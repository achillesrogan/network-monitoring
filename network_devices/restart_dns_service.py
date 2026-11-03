#!/usr/bin/env python3
"""Verify and restart the DNS service on the internal DNS server(s).

The output records the full process for each server:
  1. VERIFY   - service state, port 53 and a live query  -> DNS service DOWN
  2. EXECUTE  - the restart command and its result
  3. VERIFY   - re-check until the service answers       -> DNS service RUNNING

Servers whose DNS service is already healthy are left alone unless --force
is given.
"""
import argparse
import time

import config
import netlib

log = netlib.log


def health(session, server, service):
    running = netlib.dns_service_running(session, service)
    listening = netlib.dns_listening(session)
    status, answers = netlib.dns_query(server.fqdn, server.ip)
    log.info("    service %-8s : %s", service, "RUNNING" if running else "DOWN")
    log.info("    port 53          : %s", "listening" if listening else "not listening")
    log.info("    query %s : %s", server.fqdn, ", ".join(answers) if answers else status)
    return running and status == "OK"


def process(lab, server, force, wait):
    print()
    print("=" * 64)
    print("%s  %s  (%s)" % (server.name, server.ip, server.fqdn))
    print("=" * 64)
    try:
        session = lab.connect(server)
    except Exception as exc:
        log.error("Could not connect to %s: %s", server.name, exc)
        return {"hostname": server.name, "ip_address": server.ip, "result": "connect failed"}

    with session:
        log.info("Connected to %s (%s)", server.name, session.route)
        service = netlib.detect_dns_service(session)
        if not service:
            log.error("No DNS service (%s) found on %s", "/".join(config.DNS_SERVICE_CANDIDATES), server.name)
            return {"hostname": server.name, "ip_address": server.ip, "result": "no service"}

        log.info("[1/3] VERIFY - checking DNS service before restart")
        healthy = health(session, server, service)
        log.info("      => DNS service %s", "RUNNING" if healthy else "DOWN")
        if healthy and not force:
            log.info("      No restart required")
            return {"hostname": server.name, "ip_address": server.ip,
                    "service": service, "result": "already running"}

        log.info("[2/3] EXECUTE - restarting %s (sudo systemctl restart %s)", service, service)
        result = netlib.restart_dns_service(session, service)
        if result.ok:
            log.info("      restart command completed (exit 0)")
        else:
            log.error("      restart command failed (exit %d): %s", result.exit_code,
                      (result.stderr or result.stdout).strip())

        log.info("[3/3] VERIFY - checking DNS service after restart")
        deadline = time.time() + wait
        while True:
            healthy = health(session, server, service)
            if healthy or time.time() >= deadline:
                break
            time.sleep(2)

        if healthy:
            log.info("      => DNS service RUNNING - restart successful")
        else:
            log.error("      => DNS service still DOWN after %ds", wait)
        return {"hostname": server.name, "ip_address": server.ip, "service": service,
                "result": "restarted" if healthy else "failed", "completed_at": netlib.now()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("servers", nargs="*", help="DNS servers to process (default: all)")
    parser.add_argument("--force", action="store_true", help="restart even if the service is healthy")
    parser.add_argument("--wait", type=int, default=20, help="seconds to wait for recovery (default 20)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    netlib.setup_logging(args.verbose)

    with netlib.Lab() as lab:
        servers = [lab.device(n) for n in args.servers] if args.servers else lab.dns_servers
        results = [process(lab, s, args.force, args.wait) for s in servers]

    print()
    for r in results:
        log.info("%-6s %-13s %s", r["hostname"], r["ip_address"], r["result"])
    return 0 if all(r["result"] in ("restarted", "already running") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
