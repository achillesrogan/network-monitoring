#!/usr/bin/env python3
"""List the network device inventory from network_devices.csv.

DHCP devices are shown with the address currently leased to them by
ROUTER1, and devices excluded from automation are marked.
"""
import argparse

import netlib


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-leases", action="store_true",
                        help="don't query ROUTER1 for DHCP leases")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    netlib.setup_logging(args.verbose)

    with netlib.Lab() as lab:
        if not args.no_leases:
            lab.resolve_dhcp()

        header = ("ID", "Device", "Address", "FQDN", "Location", "Service", "OS", "Scope")
        rows = []
        for d in lab.devices:
            if d.is_dhcp:
                address = (d.leased_address + " (DHCP)") if d.leased_address else "DHCP (no lease)"
            else:
                address = d.address
            rows.append((d.device_id, d.name, address, d.fqdn or "-", d.location,
                         d.service, d.os, "excluded" if d.excluded else "in scope"))

    widths = [max(len(str(r[i])) for r in [header] + rows) for i in range(len(header))]
    line = "  ".join("{:<%d}" % w for w in widths)
    print(line.format(*header))
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print(line.format(*row))

    in_scope = sum(1 for r in rows if r[-1] == "in scope")
    print("\n%d devices (%d in scope, %d excluded)" % (len(rows), in_scope, len(rows) - in_scope))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
