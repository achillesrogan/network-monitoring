# Add a line to dns_health.log for every server whose DNS is correct.

import config
import netlib

devices = netlib.read_devices()

with open(config.LOG_FILE, "a") as log:
    for device in devices:
        name = device["Device Name"]
        ip = device["Device Address"]
        if name in config.EXCLUDED or not ip.startswith("REDACTED"):
            continue
        try:
            output = netlib.run_ssh(ip, device["Username"], device["Password"], "cat /etc/resolv.conf")
        except Exception as error:
            print(name + " - could not connect: " + str(error))
            continue

        servers = []
        for line in output.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0] == "nameserver":
                servers.append(parts[1])
        if name.startswith("DNS") and "127.0.0.1" in servers:
            servers[servers.index("127.0.0.1")] = ip

        if sorted(servers) == sorted(config.EXPECTED_DNS):
            line = netlib.now() + " | " + name + " | " + ip + " | DNS functioning correctly, not altered"
            log.write(line + "\n")
            print(line)
        else:
            print(name + " - DNS altered, not logged as healthy")
