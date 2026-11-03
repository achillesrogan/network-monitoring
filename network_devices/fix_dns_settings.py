#!/usr/bin/env python3
"""Correct the DNS client settings on every affected device from the latest scan.

Reads the affected devices from scan_results.json, connects to each one
over SSH (DHCP devices at their current lease, VLAN devices through
ROUTER1), points it at the internal DNS servers, and verifies the change.
Excluded devices are never touched. Results are written to
remediation_results.json for the resolution email.
"""
import argparse

import config
import netlib

log = netlib.log


def remediate(lab, device, expected, dry_run):
    record = {"hostname": device.name, "ip_address": device.ip or device.address}
    if device.excluded:
        record["result"] = "excluded"
        return record
    try:
        with lab.connect(device) as session:
            before = netlib.get_nameservers(session)
            record["before"] = before
            if set(before) == set(expected):
                log.info("%-8s already uses %s (%s)", device.name, ", ".join(before), session.route)
                record["result"] = "already correct"
                record["after"] = before
                return record
            if dry_run:
                log.info("%-8s would change %s -> %s", device.name, ", ".join(before) or "none",
                         ", ".join(expected))
                record["result"] = "dry run"
                return record

            result = netlib.set_nameservers(session, expected, config.DOMAIN)
            if not result.ok:
                log.error("%-8s update failed (exit %d): %s", device.name, result.exit_code,
                          (result.stderr or result.stdout).strip())
            after = netlib.get_nameservers(session)
            record["after"] = after
            record["result"] = "fixed" if set(after) == set(expected) else "failed"
            log.log(20 if record["result"] == "fixed" else 40, "%-8s %s -> %s  [%s] (%s)",
                    device.name, ", ".join(before) or "none", ", ".join(after) or "none",
                    record["result"].upper(), session.route)
    except Exception as exc:
        log.error("%-8s could not connect: %s", device.name, exc)
        record["result"] = "connect failed"
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="show changes without applying them")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    netlib.setup_logging(args.verbose)

    scan = netlib.read_json(config.SCAN_RESULTS_FILE)
    affected_names = [d["hostname"] for d in scan["affected"]]
    if not affected_names:
        log.info("Scan at %s found no affected devices - nothing to fix", scan["scanned_at"])
        return 0

    with netlib.Lab() as lab:
        lab.resolve_dhcp()
        expected = lab.nameservers
        log.info("Target DNS servers: %s (search %s)", ", ".join(expected), config.DOMAIN)
        targets = [lab.device(name) for name in affected_names]
        results = [remediate(lab, d, expected, args.dry_run) for d in targets]

    if args.dry_run:
        return 0

    ok = all(r["result"] in ("fixed", "already correct") for r in results)
    netlib.write_json(config.REMEDIATION_RESULTS_FILE, {
        "completed_at": netlib.now(),
        "scan_at": scan["scanned_at"],
        "nameservers": expected,
        "all_resolved": ok,
        "devices": results,
    })
    fixed = sum(r["result"] == "fixed" for r in results)
    log.info("Fixed: %d, already correct: %d, failed: %d", fixed,
             sum(r["result"] == "already correct" for r in results),
             sum(r["result"] not in ("fixed", "already correct") for r in results))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
