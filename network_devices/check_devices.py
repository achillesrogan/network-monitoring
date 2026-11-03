#!/usr/bin/env python3
"""Scan the network: device status and DNS verification.

For every in-scope device this checks:
  * reachability (ping from this host, falling back to ROUTER1),
  * DNS records - each device's FQDN is resolved against every internal
    DNS server and compared with its address,
  * DNS client settings - logs in over SSH and verifies the device uses the
    internal DNS servers,
  * on the DNS servers themselves, that the DNS service is running.

DHCP devices are checked at the address currently leased to them by ROUTER1.
Affected devices are written to scan_results.json for the alert, ticket and
remediation scripts.
"""
import argparse
from collections import OrderedDict

import config
import netlib

log = netlib.log


class Findings:
    """Collects issues per device, without duplicates."""

    def __init__(self):
        self.issues = OrderedDict()

    def add(self, device, issue_type, detail):
        entries = self.issues.setdefault(device.name, [])
        if not any(e["type"] == issue_type and e["detail"] == detail for e in entries):
            entries.append({"type": issue_type, "detail": detail})
            log.warning("%-8s %s - %s", device.name, issue_type, detail)

    def for_device(self, device):
        return self.issues.get(device.name, [])


def check_reachability(lab, devices, findings, status):
    log.info("--- Reachability ---")
    for device in devices:
        if not device.ip:
            status[device.name]["state"] = "NO LEASE" if device.is_dhcp else "NO ADDRESS"
            findings.add(device, "No DHCP Lease" if device.is_dhcp else "No Address",
                         "No IP address available to check")
            continue
        up, via = lab.ping(device)
        status[device.name]["state"] = "UP" if up else "DOWN"
        status[device.name]["checked_via"] = via
        if up:
            log.info("%-8s %-15s UP (%s)", device.name, device.ip, via)
        else:
            findings.add(device, "Device Unreachable", "No ping reply (%s)" % via)


def check_dns_records(lab, devices, findings, status):
    log.info("--- DNS records ---")
    servers = lab.dns_servers
    for device in devices:
        if not device.fqdn or not device.ip:
            status[device.name]["dns_records"] = "n/a"
            continue
        results = []
        for server in servers:
            result, answers = netlib.dns_query(device.fqdn, server.ip)
            if result == "NO_RESPONSE":
                findings.add(server, "DNS Server Not Responding",
                             "%s (%s) did not answer DNS queries" % (server.name, server.ip))
                results.append("%s:no-response" % server.name)
            elif result != "OK":
                findings.add(device, "DNS Record Missing",
                             "%s not found on %s (%s)" % (device.fqdn, server.name, result))
                results.append("%s:missing" % server.name)
            elif device.ip not in answers:
                findings.add(device, "DNS Record Mismatch",
                             "%s on %s returns %s, expected %s"
                             % (device.fqdn, server.name, ", ".join(answers), device.ip))
                results.append("%s:mismatch" % server.name)
            else:
                results.append("%s:ok" % server.name)
        ok = all(r.endswith(":ok") for r in results)
        status[device.name]["dns_records"] = "OK" if ok else ", ".join(results)
        if ok:
            log.info("%-8s %s resolves correctly on all DNS servers", device.name, device.fqdn)


def check_device_config(lab, devices, findings, status):
    log.info("--- DNS client settings / DNS service ---")
    expected = lab.nameservers
    for device in devices:
        entry = status[device.name]
        if entry.get("state") != "UP" or not device.has_login:
            entry["resolver"] = "not checked"
            continue
        try:
            with lab.connect(device) as session:
                entry["ssh_route"] = session.route

                if device.is_dns_server:
                    service = netlib.detect_dns_service(session)
                    entry["dns_service"] = service
                    if service is None:
                        findings.add(device, "DNS Service Down", "No DNS service installed")
                        entry["dns_service_state"] = "MISSING"
                    elif netlib.dns_service_running(session, service):
                        entry["dns_service_state"] = "RUNNING"
                        log.info("%-8s DNS service %s is running", device.name, service)
                    else:
                        entry["dns_service_state"] = "DOWN"
                        findings.add(device, "DNS Service Down",
                                     "%s service is not running" % service)

                nameservers = netlib.get_nameservers(session)
                entry["nameservers"] = nameservers
                if set(nameservers) == set(expected):
                    entry["resolver"] = "OK"
                    log.info("%-8s uses %s (%s)", device.name, ", ".join(nameservers), session.route)
                else:
                    entry["resolver"] = "WRONG"
                    findings.add(device, "DNS Misconfigured",
                                 "Uses %s, expected %s"
                                 % (", ".join(nameservers) or "no DNS servers", ", ".join(expected)))
        except Exception as exc:
            entry["resolver"] = "SSH failed"
            log.warning("%-8s SSH failed: %s", device.name, exc)


def print_report(devices, findings, status):
    print()
    header = ("Device", "IP Address", "Status", "DNS Records", "DNS Settings", "Issues")
    rows = []
    for d in devices:
        s = status[d.name]
        issues = ", ".join(sorted({i["type"] for i in findings.for_device(d)})) or "-"
        rows.append((d.name, d.ip or d.address, s.get("state", "?"),
                     s.get("dns_records", "n/a"), s.get("resolver", "n/a"), issues))
    widths = [max(len(str(r[i])) for r in [header] + rows) for i in range(len(header))]
    fmt = "  ".join("{:<%d}" % w for w in widths)
    print(fmt.format(*header))
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print(fmt.format(*row))
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-ssh", action="store_true",
                        help="skip the SSH checks (DNS client settings / DNS service)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    netlib.setup_logging(args.verbose)

    scanned_at = netlib.now()
    findings = Findings()

    with netlib.Lab() as lab:
        lab.resolve_dhcp()
        devices = lab.in_scope
        excluded = [d.name for d in lab.devices if d.excluded]
        log.info("Scanning %d devices (excluded: %s)", len(devices), ", ".join(excluded))
        log.info("Internal DNS servers: %s",
                 ", ".join("%s %s" % (d.name, d.ip) for d in lab.dns_servers))

        status = {d.name: {} for d in devices}
        check_reachability(lab, devices, findings, status)
        check_dns_records(lab, devices, findings, status)
        if not args.no_ssh:
            check_device_config(lab, devices, findings, status)
        expected = lab.nameservers

    print_report(devices, findings, status)

    results = []
    for d in devices:
        entry = d.summary()
        entry.update(status[d.name])
        entry["issues"] = findings.for_device(d)
        entry["last_checked"] = scanned_at
        results.append(entry)

    affected = [r for r in results if r["issues"]]
    netlib.write_json(config.SCAN_RESULTS_FILE, {
        "scanned_at": scanned_at,
        "expected_nameservers": expected,
        "excluded": excluded,
        "devices": results,
        "affected": affected,
    })
    log.info("%d of %d devices affected", len(affected), len(devices))
    return 1 if affected else 0


if __name__ == "__main__":
    raise SystemExit(main())
