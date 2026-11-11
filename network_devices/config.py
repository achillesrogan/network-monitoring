"""Central configuration for the network automation scripts.

Hostnames, addresses, and secrets are read from the environment when set.
Secrets have no default in source. A local .env file is loaded if present
(see .env.example); variables already set in the environment win.
"""
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

BASE_DIR = _PACKAGE_DIR

# --- Files -------------------------------------------------------------------
INVENTORY_FILE = BASE_DIR / "network_devices.csv"
SCAN_RESULTS_FILE = BASE_DIR / "scan_results.json"
REMEDIATION_RESULTS_FILE = BASE_DIR / "remediation_results.json"

# --- Network -----------------------------------------------------------------
DOMAIN = os.environ.get("NETMON_DOMAIN", "example.com")

# Segment the automation host can reach directly.
# Anything outside it is reached through ROUTER1.
SERVER_SUBNET = os.environ.get("NETMON_SERVER_SUBNET", "10.0.0.0/24")

# ROUTER1 is never analysed or changed. It is only used to read DHCP leases,
# to ping from inside the network, and as an SSH jump host into the other segments.
ROUTER_NAME = "ROUTER1"

# Devices excluded from all analysis and configuration changes.
EXCLUDED_DEVICES = {"SMTP", "SW1", "SW2", "SW3", "SW4", ROUTER_NAME}

# FQDNs as published in the network topology.
FQDNS = {
    "API": "api." + DOMAIN,
    "DB": "db." + DOMAIN,
    "DNS1": "ns2." + DOMAIN,
    "DNS2": "ns1." + DOMAIN,
    "SMTP": "smtp." + DOMAIN,
    "SVR1": "svr1." + DOMAIN,
    "SVR2": "svr2." + DOMAIN,
}

# Service each device provides, matched on the start of the device name.
SERVICES = (
    ("DNS", "DNS"),
    ("API", "Helpdesk API"),
    ("DB", "Database"),
    ("SVR", "Application Server"),
    ("PC", "Workstation"),
    ("SMTP", "SMTP"),
    ("ROUTER", "Routing"),
    ("SW", "Switching"),
)

# DNS daemons to look for on the DNS servers, in order of preference.
DNS_SERVICE_CANDIDATES = ("named", "bind9", "dnsmasq", "unbound")

# --- SSH ---------------------------------------------------------------------
SSH_PORT = int(os.environ.get("NETMON_SSH_PORT", "22"))
SSH_TIMEOUT = float(os.environ.get("NETMON_SSH_TIMEOUT", "8"))
COMMAND_TIMEOUT = float(os.environ.get("NETMON_COMMAND_TIMEOUT", "30"))

# VyOS operational-mode wrapper, needed to run "show" commands over SSH.
VYOS_OP_WRAPPER = "/opt/vyatta/bin/vyatta-op-cmd-wrapper"

# --- DNS checks --------------------------------------------------------------
DNS_QUERY_TIMEOUT = float(os.environ.get("NETMON_DNS_TIMEOUT", "3"))

# --- SMTP (no auth / no TLS unless the server you point this at requires it) -
SMTP_HOST = os.environ.get("NETMON_SMTP_HOST", "smtp." + DOMAIN)
SMTP_PORT = int(os.environ.get("NETMON_SMTP_PORT", "1025"))
MAIL_FROM = os.environ.get("NETMON_MAIL_FROM", "network-monitoring@" + DOMAIN)
MAIL_TO = [
    address.strip()
    for address in os.environ.get("NETMON_MAIL_TO", "stakeholders@" + DOMAIN).split(",")
    if address.strip()
]
MAILBOX_URL = "http://mail." + DOMAIN + ":8025/"

# --- Helpdesk API ------------------------------------------------------------
HELPDESK_API_URL = os.environ.get("NETMON_API_URL", "http://api." + DOMAIN + ":5000")
HELPDESK_TICKET_PATH = os.environ.get("NETMON_TICKET_PATH", "/api/tickets")
HELPDESK_API_TOKEN = os.environ.get("NETMON_API_TOKEN", "")
HELPDESK_DOCS_URL = "http://helpdesk." + DOMAIN + ":5000/apidocs/"
HTTP_TIMEOUT = float(os.environ.get("NETMON_HTTP_TIMEOUT", "10"))
