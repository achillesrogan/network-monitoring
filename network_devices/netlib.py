"""Shared helpers for the network automation scripts.

Provides the device inventory, SSH access (direct or through ROUTER1),
DHCP lease discovery, reachability checks, DNS queries, DNS service control
and result-file handling.
"""
from __future__ import annotations

import csv
import ipaddress
import json
import logging
import os
import platform
import re
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import config

log = logging.getLogger("netmon")

IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


# =============================================================================
# Logging / time
# =============================================================================
def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("paramiko").setLevel(logging.WARNING)


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# =============================================================================
# Inventory
# =============================================================================
@dataclass
class Device:
    device_id: str
    name: str
    address: str
    netmask: str
    location: str
    access_port: str
    os: str
    username: str
    password: str
    leased_address: Optional[str] = None

    def __repr__(self) -> str:  # never leak credentials into logs
        return "Device(%s, %s)" % (self.name, self.ip or self.address)

    @property
    def key(self) -> str:
        return self.name.upper()

    @property
    def is_dhcp(self) -> bool:
        return self.address.upper() == "DHCP"

    @property
    def has_static_ip(self) -> bool:
        return not self.is_dhcp and self.address.lower() != "none"

    @property
    def ip(self) -> Optional[str]:
        if self.is_dhcp:
            return self.leased_address
        return self.address if self.has_static_ip else None

    @property
    def excluded(self) -> bool:
        return self.key in config.EXCLUDED_DEVICES

    @property
    def has_login(self) -> bool:
        return self.username.lower() not in ("", "none")

    @property
    def is_dns_server(self) -> bool:
        return self.key.startswith("DNS")

    @property
    def is_router_os(self) -> bool:
        return self.os.upper() == "VYOS"

    @property
    def fqdn(self) -> Optional[str]:
        return config.FQDNS.get(self.key)

    @property
    def service(self) -> str:
        for prefix, service in config.SERVICES:
            if self.key.startswith(prefix):
                return service
        return "Unknown"

    @property
    def directly_reachable(self) -> bool:
        if not self.ip:
            return False
        return ipaddress.ip_address(self.ip) in ipaddress.ip_network(config.SERVER_SUBNET)

    def summary(self) -> dict:
        return {
            "hostname": self.name,
            "ip_address": self.ip or self.address,
            "service": self.service,
            "fqdn": self.fqdn,
            "addressing": "DHCP" if self.is_dhcp else "Static",
        }


def load_inventory(path: Path = config.INVENTORY_FILE) -> List[Device]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return [
            Device(
                device_id=row["Device ID"].strip(),
                name=row["Device Name"].strip(),
                address=row["Device Address"].strip(),
                netmask=row["Subnet Mask"].strip(),
                location=row["Location"].strip(),
                access_port=row["Access Port"].strip(),
                os=row["OS"].strip(),
                username=row["Username"].strip(),
                password=row["Password"].strip(),
            )
            for row in csv.DictReader(handle)
        ]


# =============================================================================
# SSH
# =============================================================================
@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


_ENV_REF = re.compile(r"^env:([A-Za-z_][A-Za-z0-9_]*)$")


def resolve_secret(value: Optional[str]) -> Optional[str]:
    """Return value, or the environment variable named by ``env:VAR_NAME``."""
    if value is None:
        return value
    match = _ENV_REF.match(value.strip())
    if not match:
        return value
    name = match.group(1)
    got = os.environ.get(name, "")
    if got == "":
        # Connection helpers report this per device and keep going.
        raise RuntimeError("Environment variable " + name + " is not set.")
    return got


def _paramiko():
    try:
        import paramiko
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("paramiko is required:  python -m pip install paramiko") from exc
    return paramiko


def _open_client(host: str, username: str, password: str, sock=None):
    username = resolve_secret(username)
    password = resolve_secret(password)
    paramiko = _paramiko()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        host,
        port=config.SSH_PORT,
        username=username,
        password=password,
        timeout=config.SSH_TIMEOUT,
        banner_timeout=config.SSH_TIMEOUT,
        auth_timeout=config.SSH_TIMEOUT,
        look_for_keys=False,
        allow_agent=False,
        sock=sock,
    )
    return client


def run_command(client, command: str, password: Optional[str] = None,
                sudo: bool = False, timeout: float = config.COMMAND_TIMEOUT) -> CommandResult:
    """Run a command over an open SSH client.

    With sudo=True the command runs under ``sudo sh -c`` and the password is
    written to sudo's stdin, so it never appears in the remote process list.
    """
    if sudo:
        command = "sudo -S -p '' sh -c " + shlex.quote(command)
    log.debug("exec: %s", command)
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    if sudo and password:
        stdin.write(resolve_secret(password) + "\n")
        stdin.flush()
    stdin.channel.shutdown_write()
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    return CommandResult(stdout.channel.recv_exit_status(), out, err)


class Session:
    """An SSH session to one device, with the route that was used."""

    def __init__(self, device: Device, client, route: str):
        self.device = device
        self.client = client
        self.route = route

    def run(self, command: str, sudo: bool = False,
            timeout: float = config.COMMAND_TIMEOUT) -> CommandResult:
        return run_command(self.client, command, self.device.password, sudo, timeout)

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "Session":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


# =============================================================================
# Lab: inventory + ROUTER1 access
# =============================================================================
class Lab:
    """The lab network: inventory, DHCP leases and SSH routing via ROUTER1."""

    def __init__(self, devices: Optional[List[Device]] = None):
        self.devices = devices if devices is not None else load_inventory()
        self._router_client = None
        self._router_failed = False
        self._leases: Optional[Dict[str, str]] = None

    # -- lookup ---------------------------------------------------------------
    def device(self, name: str) -> Device:
        for device in self.devices:
            if device.key == name.upper():
                return device
        raise KeyError("Unknown device: " + name)

    @property
    def in_scope(self) -> List[Device]:
        return [d for d in self.devices if not d.excluded]

    @property
    def dns_servers(self) -> List[Device]:
        return sorted((d for d in self.devices if d.is_dns_server),
                      key=lambda d: d.fqdn or d.name)

    @property
    def nameservers(self) -> List[str]:
        return [d.ip for d in self.dns_servers if d.ip]

    # -- router ---------------------------------------------------------------
    @property
    def router_device(self) -> Device:
        return self.device(config.ROUTER_NAME)

    def router(self):
        if self._router_client is None and not self._router_failed:
            router = self.router_device
            try:
                self._router_client = _open_client(router.ip, router.username, router.password)
                log.debug("Connected to %s (%s)", router.name, router.ip)
            except Exception as exc:
                self._router_failed = True
                log.warning("Cannot reach %s (%s): %s", router.name, router.ip, exc)
        return self._router_client

    def router_run(self, command: str) -> Optional[CommandResult]:
        client = self.router()
        if client is None:
            return None
        return run_command(client, command)

    # -- DHCP -----------------------------------------------------------------
    def dhcp_leases(self) -> Dict[str, str]:
        """Map hostname -> leased IP, read from ROUTER1's DHCP server."""
        if self._leases is None:
            result = self.router_run(config.VYOS_OP_WRAPPER + " show dhcp server leases")
            wanted = {d.key for d in self.devices if d.is_dhcp}
            self._leases = parse_dhcp_leases(result.stdout, wanted) if result else {}
        return self._leases

    def resolve_dhcp(self) -> None:
        dhcp_devices = [d for d in self.devices if d.is_dhcp]
        if not dhcp_devices:
            return
        leases = self.dhcp_leases()
        for device in dhcp_devices:
            device.leased_address = leases.get(device.key)
            if device.leased_address:
                log.debug("%s has DHCP lease %s", device.name, device.leased_address)
            else:
                log.warning("No active DHCP lease found for %s", device.name)

    # -- reachability ---------------------------------------------------------
    def ping(self, device: Device) -> Tuple[bool, str]:
        """Ping from this host; fall back to pinging from ROUTER1."""
        if not device.ip:
            return False, "no address"
        if local_ping(device.ip):
            return True, "local"
        result = self.router_run("/bin/ping -c 1 -W 1 " + shlex.quote(device.ip))
        if result is not None and result.ok:
            return True, config.ROUTER_NAME
        return False, "local+" + config.ROUTER_NAME if result is not None else "local"

    # -- SSH ------------------------------------------------------------------
    def connect(self, device: Device) -> Session:
        """Open SSH to a device: directly for the server segment, otherwise
        (or if direct fails) tunnelled through ROUTER1."""
        if not device.ip:
            raise ConnectionError("%s has no usable IP address" % device.name)
        if not device.has_login:
            raise ConnectionError("%s has no login credentials" % device.name)

        errors = []
        if device.directly_reachable:
            try:
                return Session(device, _open_client(device.ip, device.username, device.password), "direct")
            except Exception as exc:
                errors.append("direct: %s" % exc)

        router = self.router()
        if router is not None:
            try:
                channel = router.get_transport().open_channel(
                    "direct-tcpip", (device.ip, config.SSH_PORT), ("127.0.0.1", 0)
                )
                client = _open_client(device.ip, device.username, device.password, sock=channel)
                return Session(device, client, "via " + config.ROUTER_NAME)
            except Exception as exc:
                errors.append("via %s: %s" % (config.ROUTER_NAME, exc))
        else:
            errors.append("%s unavailable" % config.ROUTER_NAME)

        raise ConnectionError("; ".join(errors))

    # -- cleanup --------------------------------------------------------------
    def close(self) -> None:
        if self._router_client is not None:
            self._router_client.close()
            self._router_client = None

    def __enter__(self) -> "Lab":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def parse_dhcp_leases(output: str, wanted: Iterable[str]) -> Dict[str, str]:
    """Parse ``show dhcp server leases`` into {HOSTNAME: ip}.

    Column layouts differ between VyOS releases, so each row is matched on
    its first IPv4 address and any token equal to a wanted hostname.
    """
    wanted = {w.upper() for w in wanted}
    leases: Dict[str, str] = {}
    for line in output.splitlines():
        match = re.match(r"\s*((?:\d{1,3}\.){3}\d{1,3})\s", line)
        if not match or "expired" in line.lower():
            continue
        for token in line.split():
            name = token.split(".")[0].upper()
            if name in wanted:
                leases[name] = match.group(1)
                break
    return leases


# =============================================================================
# Reachability and DNS
# =============================================================================
def local_ping(ip: str) -> bool:
    if platform.system() == "Windows":
        command = ["ping", "-n", "1", "-w", "1000", ip]
    else:
        command = ["ping", "-c", "1", "-W", "1", ip]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return False
    # Windows can return 0 for "Destination host unreachable"; require a TTL.
    return result.returncode == 0 and "TTL=" in result.stdout.upper()


def dns_query(name: str, server: str,
              timeout: float = config.DNS_QUERY_TIMEOUT) -> Tuple[str, List[str]]:
    """Query one DNS server for an A record.

    Returns (status, addresses) where status is OK, NXDOMAIN, NOANSWER or
    NO_RESPONSE.
    """
    try:
        import dns.exception
        import dns.resolver
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("dnspython is required:  python -m pip install dnspython") from exc

    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = [server]
    resolver.lifetime = timeout
    try:
        answer = resolver.resolve(name, "A")
        return "OK", sorted(record.to_text() for record in answer)
    except dns.resolver.NXDOMAIN:
        return "NXDOMAIN", []
    except dns.resolver.NoAnswer:
        return "NOANSWER", []
    except (dns.exception.Timeout, dns.resolver.NoNameservers):
        return "NO_RESPONSE", []


# =============================================================================
# Remote DNS client settings
# =============================================================================
_RESOLVED_ACTIVE = "systemctl is-active --quiet systemd-resolved 2>/dev/null"


def get_nameservers(session: Session) -> List[str]:
    """Return the DNS servers a Linux host is actually configured to use."""
    if session.device.is_router_os:
        result = session.run("cat /etc/resolv.conf")
        return _nameserver_lines(result.stdout)
    script = (
        "if %s; then echo MODE=resolved; resolvectl dns 2>/dev/null; "
        "else echo MODE=file; cat /etc/resolv.conf; fi" % _RESOLVED_ACTIVE
    )
    output = session.run(script).stdout
    if output.startswith("MODE=resolved"):
        servers: List[str] = []
        for ip in IPV4_RE.findall(output):
            if ip not in servers:
                servers.append(ip)
        return servers
    return _nameserver_lines(output)


def _nameserver_lines(text: str) -> List[str]:
    servers = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "nameserver":
            servers.append(parts[1])
    return servers


def set_nameservers(session: Session, nameservers: List[str], domain: str) -> CommandResult:
    """Point a Linux host at the given DNS servers (requires sudo).

    Handles both systemd-resolved hosts and plain /etc/resolv.conf hosts,
    and keeps a timestamped backup of the previous resolv.conf.
    """
    ns_list = " ".join(nameservers)
    lines = ["search " + domain] + ["nameserver " + ns for ns in nameservers]
    printf_args = " ".join(shlex.quote(line) for line in lines)
    script = (
        "set -e; "
        "cp -aL /etc/resolv.conf /etc/resolv.conf.bak.$(date +%Y%m%d%H%M%S) 2>/dev/null || true; "
        "if " + _RESOLVED_ACTIVE + "; then "
        "  mkdir -p /etc/systemd/resolved.conf.d; "
        "  printf '[Resolve]\\nDNS=%s\\nDomains=%s\\n' " + shlex.quote(ns_list) + " " + shlex.quote(domain)
        + " > /etc/systemd/resolved.conf.d/lab-dns.conf; "
        "  systemctl restart systemd-resolved; "
        "  IFACE=$(ip route show default | awk '{print $5; exit}'); "
        "  [ -n \"$IFACE\" ] && resolvectl dns \"$IFACE\" " + ns_list + " || true; "
        "else "
        "  [ -L /etc/resolv.conf ] && rm -f /etc/resolv.conf; "
        "  printf '%s\\n' " + printf_args + " > /etc/resolv.conf; "
        "fi"
    )
    return session.run(script, sudo=True)


# =============================================================================
# DNS service control (on the DNS servers)
# =============================================================================
def detect_dns_service(session: Session) -> Optional[str]:
    candidates = " ".join(config.DNS_SERVICE_CANDIDATES)
    script = (
        "for s in %s; do "
        "if systemctl cat \"$s.service\" >/dev/null 2>&1 || [ -x \"/etc/init.d/$s\" ]; "
        "then echo \"$s\"; exit 0; fi; done; exit 1" % candidates
    )
    result = session.run(script)
    return result.stdout.strip() or None if result.ok else None


def _service_cmd(action: str, service: str) -> str:
    svc = shlex.quote(service)
    if action == "status":
        systemd, sysv = "systemctl is-active --quiet " + svc, "service " + svc + " status >/dev/null 2>&1"
    else:
        systemd, sysv = "systemctl " + action + " " + svc, "service " + svc + " " + action
    return "if [ -d /run/systemd/system ]; then %s; else %s; fi" % (systemd, sysv)


def dns_service_running(session: Session, service: str) -> bool:
    return session.run(_service_cmd("status", service)).ok


def restart_dns_service(session: Session, service: str) -> CommandResult:
    return session.run(_service_cmd("restart", service), sudo=True, timeout=60)


def dns_listening(session: Session) -> bool:
    result = session.run(
        "(ss -lntu 2>/dev/null || netstat -lntu 2>/dev/null) | grep -Eq '[:.]53[[:space:]]'"
    )
    return result.ok


# =============================================================================
# Email
# =============================================================================
def send_email(subject: str, body: str, recipients: Optional[List[str]] = None,
               dry_run: bool = False) -> bool:
    import smtplib
    from email.message import EmailMessage
    from email.utils import formatdate, make_msgid

    recipients = recipients or config.MAIL_TO
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.MAIL_FROM
    message["To"] = ", ".join(recipients)
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=config.DOMAIN)
    message.set_content(body)

    if dry_run:
        print("From: %s\nTo: %s\nSubject: %s\n\n%s" % (message["From"], message["To"], subject, body))
        log.info("Dry run - email not sent")
        return True

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as smtp:
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        log.error("Could not send email via %s:%s - %s", config.SMTP_HOST, config.SMTP_PORT, exc)
        return False
    log.info("Email sent to %s via %s:%s (view at %s)", ", ".join(recipients),
             config.SMTP_HOST, config.SMTP_PORT, config.MAILBOX_URL)
    return True


# =============================================================================
# Result files
# =============================================================================
def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    log.info("Results written to %s", path.name)


def read_json(path: Path) -> dict:
    if not path.exists():
        raise SystemExit("%s not found - run the earlier step first." % path.name)
    return json.loads(path.read_text(encoding="utf-8"))
