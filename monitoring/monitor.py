# Run the monitoring scripts over and over, every CHECK_INTERVAL seconds.
# Stop it with Ctrl+C.

import subprocess
import sys
import time

import config

scripts = ["check_availability.py", "create_unavailable_tickets.py",
           "dns_monitor.py", "dns_health_log.py"]

while True:
    print("========== Monitoring check ==========")
    for script in scripts:
        print("--- " + script)
        subprocess.run([sys.executable, script])
    print("Waiting " + str(config.CHECK_INTERVAL) + " seconds...")
    time.sleep(config.CHECK_INTERVAL)
