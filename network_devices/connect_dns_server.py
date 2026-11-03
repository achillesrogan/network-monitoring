#!/usr/bin/env python3
"""Connect to the internal DNS server(s) and report the DNS service state.

For each DNS server: opens an SSH session, identifies the host and DNS
daemon, checks the service state and port 53, and runs a live DNS query.
"""
import argparse

import netlib

log = netlib.log


def inspect(lab, server):
    print("=" * 60)
    print("%s  %s  (%s)" % (server.name, server.ip, server.fqdn))
    print("=" * 60)
    try:
        with lab.connect(server) as session:
            log.info("Connected to %s (%s)", server.name, session.route)
            hostname = session.run("hostname").stdout.strip()
            kernel = session.run("uname -sr").stdout.strip()
            service = netlib.detect_dns_service(session)
            running = bool(service) and netlib.dns_service_running(session, service)
            listening = netlib.dns_listening(session)
    except Exception as exc:
        log.error("Could not connect to %s: %s", server.name, exc)
        return False

    status, answers = netlib.dns_query(server.fqdn, server.ip)
    healthy = running and status == "OK"
    print("  Checked at    : %s" % netlib.now())
    print("  Hostname      : %s" % hostname)
    print("  Kernel        : %s" % kernel)
    print("  DNS service   : %s" % (service or "not found"))
    print("  Service state : %s" % ("RUNNING" if running else "DOWN"))
    print("  Port 53       : %s" % ("listening" if listening else "not listening"))
    print("  Test query    : %s -> %s" % (server.fqdn, ", ".join(answers) if answers else status))
    if healthy:
        print("  RESULT        : DNS service is RUNNING - no restart required")
    else:
        print("  RESULT        : DNS service is DOWN - restart required "
              "(run restart_dns_service.py %s)" % server.name)
    print()
    return healthy


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("servers", nargs="*", help="DNS servers to check (default: all)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    netlib.setup_logging(args.verbose)

    print("DNS SERVICE STATUS VERIFICATION")
    print("Connects to each internal DNS server over SSH and verifies the DNS")
    print("service before any restart is attempted.\n")

    with netlib.Lab() as lab:
        servers = [lab.device(n) for n in args.servers] if args.servers else lab.dns_servers
        healthy = [inspect(lab, s) for s in servers]

    log.info("%d of %d DNS server(s) healthy", sum(healthy), len(healthy))
    down = [s.name for s, ok in zip(servers, healthy) if not ok]
    if down:
        log.warning("DNS service DOWN on: %s - restart required", ", ".join(down))
    return 0 if all(healthy) else 1


if __name__ == "__main__":
    raise SystemExit(main())