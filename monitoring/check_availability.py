# Ping each device and email stakeholders about any that are down.
# The names of unavailable devices are saved for create_unavailable_tickets.py.

import config
import monitoring
import netlib

devices = netlib.read_devices()
unavailable = []

print("Checking device availability...")
for device in devices:
    name = device["Device Name"]
    ip = device["Device Address"]

    # Skip excluded devices, and devices without a fixed IP (DHCP / None)
    if name in config.EXCLUDED or ip in ("DHCP", "None"):
        continue

    if netlib.ping(ip):
        print(name + " (" + ip + ") - UP")
    else:
        print(name + " (" + ip + ") - UNAVAILABLE")
        unavailable.append(name + "," + ip)
        subject = monitoring.UNAVAILABLE_SUBJECT.format(name=name, ip=ip)
        body = monitoring.UNAVAILABLE_BODY.format(name=name, ip=ip, time=netlib.now())
        netlib.send_email(subject, body)

# Save the unavailable devices for the ticket script
with open(config.UNAVAILABLE_FILE, "w") as file:
    for line in unavailable:
        file.write(line + "\n")

print("Unavailable devices: " + str(len(unavailable)))
