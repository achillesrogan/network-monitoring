"""Central configuration for the network automation scripts.

Every value can be overridden with an environment variable so secrets and
lab-specific addresses don't have to be edited in source control.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# --- Files -------------------------------------------------------------------
INVENTORY_FILE = BASE_DIR / "network_devices.csv"
SCAN_RESULTS_FILE = BASE_DIR / "scan_results.json"
REMEDIATION_RESULTS_FILE = BASE_DIR / "remediation_results.json"

# --- Network -----------------------------------------------------------------
DOMAIN = "REDACTED"

# Segment the automation host can reach directly (HOST -> SERVERS).
# Anything outside it (REDACTED) is reached through ROUTER1.
SERVER_SUBNET = "REDACTED"

# ROUTER1 is never analysed or changed. It is only used to read DHCP leases,
# to ping from inside the network, and as an SSH jump host into the VLANs.
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

# --- SMTP (MailHog, no auth / no TLS) -----------------------------------------
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
HELPDESK_API_TOKEN = os.environ.get(
    "NETMON_API_TOKEN", "REDACTED"
)
HELPDESK_DOCS_URL = "http://helpdesk." + DOMAIN + ":5000/apidocs/"
HTTP_TIMEOUT = float(os.environ.get("NETMON_HTTP_TIMEOUT", "10"))
