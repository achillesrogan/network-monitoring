# Network Device Monitoring & DNS Automation

Python tooling that watches a lab network inventory, alerts on outages and DNS drift, opens helpdesk tickets, and remediates incorrect DNS client settings.

The repo has two related packages that share the same inventory (`network_devices.csv`) and the same problem space—reachability, DNS health, SMTP alerts, and ticket workflows.

## What's included

### `monitoring/` — monitoring loop

Straightforward scripts meant to be run on a schedule (or via `monitor.py`):

| Script | Purpose |
| --- | --- |
| `read_devices.py` | Print the device inventory from CSV |
| `check_availability.py` | Ping in-scope devices; email when a host is down |
| `create_unavailable_tickets.py` | Open helpdesk tickets for unavailable devices |
| `dns_monitor.py` | Detect altered DNS settings, alert, ticket, auto-correct, close ticket |
| `dns_health_log.py` | Append healthy DNS checks to `dns_health.log` |
| `backup_dns_config.py` | Back up BIND config from the DNS servers into `DNS-Backup/` |
| `monitor.py` | Run the availability and DNS checks on a repeating interval |
| `monitoring.py` | Email subject/body templates |
| `config.py` / `netlib.py` | Shared settings and helpers (CSV, ping, SSH, SMTP) |

### `network_devices/` — fuller automation suite

A more structured set of CLI tools built on a shared `netlib` lab helper (SSH, DHCP lease lookup via the router, DNS queries):

| Script | Purpose |
| --- | --- |
| `network_devices.py` | List inventory (with optional DHCP lease resolution) |
| `check_devices.py` | Scan reachability, DNS records, client DNS settings, and DNS service status; write `scan_results.json` |
| `send_alert_email.py` / `send_resolution_email.py` | Stakeholder notifications |
| `create_tickets.py` | Helpdesk tickets from scan findings |
| `fix_dns_settings.py` | Restore expected nameserver configuration |
| `restart_dns_service.py` | Restart DNS daemons on the name servers |
| `connect_dns_server.py` | Interactive / scripted DNS server connectivity helpers |
| `config.py` | Settings with environment-variable overrides for hosts and secrets |

## Requirements

- Python 3.10+
- Network access to the lab hosts (ping / SSH / SMTP / helpdesk API as configured)
- Dependencies for `network_devices/`:

```bash
pip install -r network_devices/requirements.txt
```

(`paramiko`, `dnspython`, `requests`)

For `monitoring/`, install the same libraries used by the scripts (`paramiko`, `requests`).

## Configuration

Both packages read device rows from `network_devices.csv` (ID, name, address, credentials, OS, and so on).

Shared ideas across configs:

- Expected internal DNS servers (default `REDACTED` / `REDACTED`)
- Devices excluded from checks (e.g. switches, SMTP, router)
- SMTP endpoint for alert mail
- Helpdesk API URL and bearer token

In `network_devices/`, prefer environment variables (`NETMON_SMTP_HOST`, `NETMON_API_TOKEN`, etc.) instead of editing secrets into source.

## Typical workflow

**Monitoring loop**

```bash
cd monitoring
python backup_dns_config.py          # optional one-time / periodic backup
python monitor.py                    # repeating availability + DNS checks
```

**Automation suite pipeline**

```bash
cd network_devices
python check_devices.py
python send_alert_email.py
python create_tickets.py
python fix_dns_settings.py
python send_resolution_email.py
```

## Notes

- Scripts that change DNS or restart services require working SSH credentials from the CSV (or lab equivalents).
- Keep API tokens and passwords out of public remotes when you can; use env overrides in `network_devices/config.py`.
