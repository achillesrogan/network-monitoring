# Network Device Monitoring & DNS Automation

Python tooling that watches a network inventory, alerts on outages and DNS drift, opens helpdesk tickets, and remediates incorrect DNS client settings.

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

A more structured set of CLI tools built on a shared `netlib` helper (SSH, DHCP lease lookup via the router, DNS queries):

| Script | Purpose |
| --- | --- |
| `network_devices.py` | List inventory (with optional DHCP lease resolution) |
| `check_devices.py` | Scan reachability, DNS records, client DNS settings, and DNS service status; write `scan_results.json` |
| `send_alert_email.py` / `send_resolution_email.py` | Stakeholder notifications |
| `create_tickets.py` | Helpdesk tickets from scan findings |
| `fix_dns_settings.py` | Restore expected nameserver configuration |
| `restart_dns_service.py` | Restart DNS daemons on the name servers |
| `connect_dns_server.py` | Interactive / scripted DNS server connectivity helpers |
| `config.py` | Settings loaded from the environment |

## Requirements

- Python 3.10+
- Network access to the hosts (ping / SSH / SMTP / helpdesk API as configured)
- Dependencies for `network_devices/`:

```bash
pip install -r network_devices/requirements.txt
```

(`paramiko`, `dnspython`, `requests`)

For `monitoring/`, install the same libraries used by the scripts (`paramiko`, `requests`).

## Configuration

Copy `.env.example` to `.env` (that file is gitignored) or export the same variables. Both packages load `.env` from the repo root and from the package directory. Variables already set in the environment win.

The Helpdesk bearer token is `NETMON_API_TOKEN`. It has no default in source. Device SSH usernames and passwords are not stored in git: `network_devices.csv` references them as `env:VARIABLE_NAME` (for example `env:NETMON_SSH_PASSWORD`).

The committed inventory is an example. Addresses are documentation ranges (`10.0.0.0/24`, `192.168.1.0/24`, `192.168.2.0/24`) and the domain is `example.com`. Point the tools at a real network with `NETMON_DOMAIN`, `NETMON_SERVER_SUBNET`, and `NETMON_EXPECTED_DNS`, and replace the example rows in a private copy of the CSV if you need different hosts.

Shared settings:

- Expected DNS servers (default `10.0.0.10` / `10.0.0.20`)
- Devices excluded from checks (switches, SMTP, router)
- SMTP endpoint for alert mail
- Helpdesk API URL and bearer token

## Secret scanning

`.pre-commit-config.yaml` runs gitleaks on staged changes. `.github/workflows/gitleaks.yml` runs gitleaks on pushes and pull requests. Install the hook with `pre-commit install` after `pip install pre-commit`.

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

- Scripts that change DNS or restart services need the SSH variables named in the CSV (`NETMON_SSH_USER`, `NETMON_SSH_PASSWORD`, `NETMON_ROUTER_USER`, `NETMON_ROUTER_PASSWORD`).
- Ticket scripts exit if `NETMON_API_TOKEN` is unset.
