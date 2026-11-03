# Shared settings for the monitoring scripts.

# The device list
CSV_FILE = "network_devices.csv"

# The internal DNS servers every device should use
EXPECTED_DNS = ["REDACTED", "REDACTED"]

# Email (lab SMTP / MailHog)
SMTP_HOST = "smtp.REDACTED"
SMTP_PORT = 1025
EMAIL_FROM = "REDACTED"
EMAIL_TO = "REDACTED"

# Helpdesk API
API_URL = "http://api.REDACTED:5000/api/tickets"
API_TOKEN = "REDACTED"

# Files the scripts create
BACKUP_FOLDER = "DNS-Backup"
LOG_FILE = "dns_health.log"
UNAVAILABLE_FILE = "unavailable_devices.txt"

# Devices we must not check or change
EXCLUDED = ["SMTP", "SW1", "SW2", "SW3", "SW4", "ROUTER1"]

# How many seconds to wait between checks in monitor.py
CHECK_INTERVAL = 60
