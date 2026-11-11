# Shared settings for the monitoring scripts.
#
# Secrets and lab-specific hosts come from the environment. A .env file in
# this directory or the repo root is loaded when present. Variables that are
# already set in the environment are left alone.

import ipaddress
import os
from pathlib import Path


def _load_env_files(*paths):
    merged = {}
    for path in paths:
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            if key:
                merged[key] = value
    for key, value in merged.items():
        os.environ.setdefault(key, value)


_PACKAGE_DIR = Path(__file__).resolve().parent
_load_env_files(_PACKAGE_DIR.parent / ".env", _PACKAGE_DIR / ".env")

# The device list
CSV_FILE = "network_devices.csv"

DOMAIN = os.environ.get("NETMON_DOMAIN", "example.com")
SERVER_SUBNET = os.environ.get("NETMON_SERVER_SUBNET", "10.0.0.0/24")
EXPECTED_DNS = [
    item.strip()
    for item in os.environ.get("NETMON_EXPECTED_DNS", "10.0.0.10,10.0.0.20").split(",")
    if item.strip()
]

# Email
SMTP_HOST = os.environ.get("NETMON_SMTP_HOST", "smtp." + DOMAIN)
SMTP_PORT = int(os.environ.get("NETMON_SMTP_PORT", "1025"))
EMAIL_FROM = os.environ.get("NETMON_MAIL_FROM", "network-monitoring@" + DOMAIN)
EMAIL_TO = os.environ.get("NETMON_MAIL_TO", "stakeholders@" + DOMAIN)

# Helpdesk API. NETMON_API_URL is the origin; the ticket path is appended.
_API_BASE = os.environ.get("NETMON_API_URL", "http://api." + DOMAIN + ":5000").rstrip("/")
_TICKET_PATH = os.environ.get("NETMON_TICKET_PATH", "/api/tickets")
API_URL = _API_BASE + "/" + _TICKET_PATH.lstrip("/")
API_TOKEN = os.environ.get("NETMON_API_TOKEN", "")

# Files the scripts create
BACKUP_FOLDER = "DNS-Backup"
LOG_FILE = "dns_health.log"
UNAVAILABLE_FILE = "unavailable_devices.txt"

# Devices we must not check or change
EXCLUDED = ["SMTP", "SW1", "SW2", "SW3", "SW4", "ROUTER1"]

# How many seconds to wait between checks in monitor.py
CHECK_INTERVAL = 60


def in_server_subnet(ip):
    # True when ip is a host inside the configured server subnet.
    try:
        return ipaddress.ip_address(ip) in ipaddress.ip_network(SERVER_SUBNET, strict=False)
    except ValueError:
        return False


def require_api_token():
    if not API_TOKEN:
        raise SystemExit("NETMON_API_TOKEN is not set.")
    return API_TOKEN
