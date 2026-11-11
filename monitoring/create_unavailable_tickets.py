# Create a Helpdesk ticket for each unavailable device.
# Run check_availability.py first - it saves the list of unavailable devices.

import requests

import config

headers = {"Authorization": "Bearer " + config.API_TOKEN}

with open(config.UNAVAILABLE_FILE, "r") as file:
    lines = file.read().splitlines()

if len(lines) == 0:
    print("No unavailable devices - no tickets needed.")
else:
    config.require_api_token()

for line in lines:
    name, ip = line.split(",")
    ticket = {
        "title": "Device Unavailable - " + name + " (" + ip + ")",
        "description": "Issue type: Device Unavailable\nDevice: " + name + " (" + ip + ")",
        "priority": "high",
    }
    response = requests.post(config.API_URL, json=ticket, headers=headers, timeout=10)
    if response.status_code == 201:
        print("Ticket #" + str(response.json()["id"]) + " created for " + name)
    else:
        print("Ticket failed for " + name + ": " + str(response.status_code) + " " + response.text)
