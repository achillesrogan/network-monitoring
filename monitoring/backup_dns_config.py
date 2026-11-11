# Back up the DNS record configuration of both DNS servers.
#
# Creates:
#   DNS-Backup/Server-1/record-config.txt   (DNS1)
#   DNS-Backup/Server-2/record-config.txt   (DNS2)

import os

import config
import netlib

# Zone file that holds the records for the configured domain
ZONE_FILE = "/etc/bind/zones/db." + config.DOMAIN

devices = netlib.read_devices()

# Find the DNS servers in the CSV file
dns_servers = []
for device in devices:
    if device["Device Name"].startswith("DNS"):
        dns_servers.append(device)

server_number = 1
for server in dns_servers:
    name = server["Device Name"]
    ip = server["Device Address"]
    folder = os.path.join(config.BACKUP_FOLDER, "Server-" + str(server_number))
    os.makedirs(folder, exist_ok=True)

    print("Backing up " + name + " (" + ip + ") to " + folder)
    try:
        named_conf = netlib.run_ssh(ip, server["Username"], server["Password"],
                                    "cat /etc/bind/named.conf.local")
        records = netlib.run_ssh(ip, server["Username"], server["Password"],
                                 "cat " + ZONE_FILE)
    except Exception as error:
        print("    Could not back up " + name + ": " + str(error))
        server_number = server_number + 1
        continue

    # Write the record configuration file
    with open(os.path.join(folder, "record-config.txt"), "w") as file:
        file.write("; Backup of " + name + " (" + ip + ") taken " + netlib.now() + "\n\n")
        file.write("; ---- named.conf.local ----\n")
        file.write(named_conf + "\n")
        file.write("; ---- " + ZONE_FILE + " ----\n")
        file.write(records)

    print("    Saved " + os.path.join(folder, "record-config.txt"))
    server_number = server_number + 1
