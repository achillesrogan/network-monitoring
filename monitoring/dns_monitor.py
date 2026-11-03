# Check each server's DNS setting. If it was altered:
#   1. email the "DNS Setting Altered Notification"
#   2. open a ticket
#   3. correct the DNS setting
#   4. update the ticket to show it is resolved
#


import requests

import config
import monitoring
import netlib

headers = {"Authorization": "Bearer " + config.API_TOKEN}
devices = netlib.read_devices()

for device in devices:
    name = device["Device Name"]
    ip = device["Device Address"]
    if name in config.EXCLUDED or not ip.startswith("REDACTED"):
        continue

    user = device["Username"]
    password = device["Password"]
    try:
        output = netlib.run_ssh(ip, user, password, "cat /etc/resolv.conf")
    except Exception as error:
        print(name + " - could not connect: " + str(error))
        continue

    # Collect the "nameserver" lines
    servers = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == "nameserver":
            servers.append(parts[1])

    # A DNS server may list itself as 127.0.0.1
    if name.startswith("DNS") and "127.0.0.1" in servers:
        servers[servers.index("127.0.0.1")] = ip

    if sorted(servers) == sorted(config.EXPECTED_DNS):
        print(name + " - DNS OK " + str(servers))
        continue

    print(name + " - DNS ALTERED " + str(servers))

    # 1. Email
    subject = monitoring.ALTERED_SUBJECT.format(name=name, ip=ip)
    body = monitoring.ALTERED_BODY.format(name=name, ip=ip, detected=", ".join(servers),
                                          expected=", ".join(config.EXPECTED_DNS),
                                          time=netlib.now())
    netlib.send_email(subject, body)

    # 2. Ticket
    ticket = {"title": "DNS Setting Altered - " + name + " (" + ip + ")",
              "description": "Detected: " + ", ".join(servers),
              "priority": "high"}
    response = requests.post(config.API_URL, json=ticket, headers=headers, timeout=10)
    ticket_id = response.json()["id"]
    print("    Ticket #" + str(ticket_id) + " created")

    # 3. Correct the DNS setting
    new_file = "nameserver " + config.EXPECTED_DNS[0] + "\\nnameserver " + config.EXPECTED_DNS[1]
    command = "echo " + password + " | sudo -S sh -c 'printf \"" + new_file + "\\n\" > /etc/resolv.conf'"
    netlib.run_ssh(ip, user, password, command)
    print("    DNS setting corrected")

    # 4. Update the ticket
    response = requests.patch(config.API_URL + "/" + str(ticket_id),
                              json={"status": "closed"}, headers=headers, timeout=10)
    print("    Ticket #" + str(ticket_id) + " updated: " + str(response.status_code))
