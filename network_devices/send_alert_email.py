#!/usr/bin/env python3
"""Send an incident alert email for every affected device from the latest scan.

Lists each affected device by hostname, IP address and service.
"""
import argparse

import config
import netlib

SUBJECT = "URGENT: Device Compromise Detected—Immediate Attention Required"

TEMPLATE = """\
Dear Stakeholders,

This is an automated alert to inform you that the following device(s) have been identified as compromised during the recent network scan:

{device_blocks}
Immediate investigation and remediation are recommended to prevent further impact.

If you have any questions or require additional information, please contact the IT support team.

Best regards,

Network Monitoring System
"""

DEVICE_BLOCK = """\
Device Name: {hostname}
IP Address: {ip_address}
Service: {service}
Issue(s): {issues}
Last Checked: {last_checked}
"""


def build_body(affected):
    blocks = "\n".join(
        DEVICE_BLOCK.format(
            hostname=d["hostname"],
            ip_address=d["ip_address"],
            service=d["service"],
            issues="; ".join("%s (%s)" % (i["type"], i["detail"]) for i in d["issues"]),
            last_checked=d["last_checked"],
        )
        for d in affected
    )
    return TEMPLATE.format(device_blocks=blocks)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--to", nargs="+", help="override recipients (default: %s)"
                        % ", ".join(config.MAIL_TO))
    parser.add_argument("--dry-run", action="store_true", help="print the email instead of sending")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    netlib.setup_logging(args.verbose)

    scan = netlib.read_json(config.SCAN_RESULTS_FILE)
    affected = scan["affected"]
    if not affected:
        netlib.log.info("Scan at %s found no affected devices - no alert sent", scan["scanned_at"])
        return 0

    netlib.log.info("Alerting stakeholders about %d device(s): %s", len(affected),
                    ", ".join(d["hostname"] for d in affected))
    sent = netlib.send_email(SUBJECT, build_body(affected), args.to, args.dry_run)
    return 0 if sent else 1


if __name__ == "__main__":
    raise SystemExit(main())
