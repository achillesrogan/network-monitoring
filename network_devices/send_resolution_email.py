#!/usr/bin/env python3
"""Send a resolution notification email once remediation is complete.

Lists every affected device by hostname and IP address. Refuses to send
if remediation_results.json shows unresolved devices, unless --force is given.
"""
import argparse

import config
import netlib

log = netlib.log

SUBJECT = "RESOLVED: DNS Service Issue and Device Compromise—All Issues Remediated"

TEMPLATE = """\
Dear Stakeholders,

This is an automated notification to inform you that the DNS service issue and all related device compromises have been successfully resolved. The following devices were affected and have now been remediated:

{device_list}

No further action is required at this time. If you have any questions or concerns, please contact the IT support team.

Thank you for your attention.

Best regards,

Network Monitoring System
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--to", nargs="+", help="override recipients (default: %s)"
                        % ", ".join(config.MAIL_TO))
    parser.add_argument("--force", action="store_true", help="send even if some devices are unresolved")
    parser.add_argument("--dry-run", action="store_true", help="print the email instead of sending")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    netlib.setup_logging(args.verbose)

    # The remediation record holds every device affected in the scan, so
    # the list survives a re-scan that overwrites scan_results.json.
    remediation = netlib.read_json(config.REMEDIATION_RESULTS_FILE)
    affected = remediation["devices"]
    if not affected:
        log.info("No affected devices were remediated - no email sent")
        return 0

    if not remediation["all_resolved"] and not args.force:
        unresolved = [d["hostname"] for d in affected
                      if d["result"] not in ("fixed", "already correct")]
        log.error("Remediation incomplete for: %s - fix these or use --force", ", ".join(unresolved))
        return 1

    width = max(len(d["hostname"]) for d in affected)
    device_list = "\n".join(
        "- Hostname: %-*s  IP Address: %s" % (width, d["hostname"], d["ip_address"]) for d in affected
    )

    log.info("Notifying stakeholders that %d device(s) are remediated", len(affected))
    sent = netlib.send_email(SUBJECT, TEMPLATE.format(device_list=device_list), args.to, args.dry_run)
    return 0 if sent else 1


if __name__ == "__main__":
    raise SystemExit(main())
