# Email subject/body templates. Other scripts fill {placeholders} with .format().

UNAVAILABLE_SUBJECT = "Network Device Unavailable: {name} ({ip})"
UNAVAILABLE_BODY = """Dear Network Administrator,

This is an automated notification that the following network device is currently unavailable:

Device Name: {name}

IP Address: {ip}

Last Checked: {time}

Please investigate this issue at your earliest convenience.

Best regards,

Network Monitoring System
"""

ALTERED_SUBJECT = "DNS Configuration Alert: {name} ({ip})"
ALTERED_BODY = """Dear Network Administrator,

This is an automated alert that the DNS configuration for the following device has been altered from the expected settings:

Device Name: {name}

IP Address: {ip}

Detected DNS Setting: {detected}

Expected DNS Setting: {expected}

Time Detected: {time}

The system will attempt to automatically correct this configuration.

Best regards,

Network Monitoring System
"""
