#!/usr/bin/env python3
"""Create a Helpdesk ticket for each affected device from the latest scan.

Each ticket states the type of issue and the targeted device. Tickets are
sent to the Helpdesk API with Bearer-token authentication.

Use --show-api to list the endpoints published in the API documentation.
"""
import argparse
import json

import config
import netlib

log = netlib.log

# Highest-priority issue first; it becomes the ticket's issue type.
SEVERITY = (
    "DNS Service Down",
    "DNS Server Not Responding",
    "DNS Misconfigured",
    "DNS Record Mismatch",
    "DNS Record Missing",
    "Device Unreachable",
    "No DHCP Lease",
)

# API accepts: low, medium, high, urgent
PRIORITY = {
    "DNS Service Down": "urgent",
    "DNS Server Not Responding": "urgent",
    "DNS Misconfigured": "high",
    "DNS Record Mismatch": "high",
    "DNS Record Missing": "high",
    "Device Unreachable": "high",
    "No DHCP Lease": "medium",
}


def _requests():
    try:
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("requests is required:  python -m pip install requests") from exc
    return requests, HTTPAdapter, Retry


def api_session():
    requests, HTTPAdapter, Retry = _requests()
    session = requests.Session()
    headers = {"Accept": "application/json"}
    if config.HELPDESK_API_TOKEN:
        headers["Authorization"] = "Bearer " + config.HELPDESK_API_TOKEN
    session.headers.update(headers)
    retry = Retry(total=3, backoff_factor=1, status_forcelist=(502, 503, 504),
                  allowed_methods=frozenset({"GET", "POST"}))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def primary_issue(issues):
    types = [i["type"] for i in issues]
    for issue_type in SEVERITY:
        if issue_type in types:
            return issue_type
    return types[0]


def build_ticket(device, scanned_at):
    issue_type = primary_issue(device["issues"])
    details = "\n".join("- %s: %s" % (i["type"], i["detail"]) for i in device["issues"])
    return {
        "title": "%s - %s (%s)" % (issue_type, device["hostname"], device["ip_address"]),
        "issue_type": issue_type,
        "priority": PRIORITY.get(issue_type, "medium"),
        "description": (
                "Automated network scan at %s identified %s (%s, %s service) as compromised.\n\n%s"
                % (scanned_at, device["hostname"], device["ip_address"], device["service"], details)
        ),
        "devices": [{
            "hostname": device["hostname"],
            "ip_address": device["ip_address"],
            "service": device["service"],
        }],
    }


def show_api(session):
    """Print the endpoints in the Helpdesk API's Swagger spec."""
    base = config.HELPDESK_DOCS_URL.split("/apidocs")[0]
    for path in ("/apispec_1.json", "/swagger.json", "/openapi.json"):
        try:
            response = session.get(base + path, timeout=config.HTTP_TIMEOUT)
        except Exception as exc:
            log.debug("%s: %s", path, exc)
            continue
        if response.ok:
            spec = response.json()
            print("Spec: %s%s\n" % (base, path))
            for route, methods in spec.get("paths", {}).items():
                for method, info in methods.items():
                    if not isinstance(info, dict):
                        continue
                    print("%-6s %-30s %s" % (method.upper(), route, info.get("summary", "")))
                    # Full request details for anything that creates tickets
                    if method.lower() == "post" and "ticket" in route.lower():
                        detail = {k: info[k] for k in ("parameters", "requestBody", "responses") if k in info}
                        print(json.dumps(detail, indent=2))
            schemas = spec.get("definitions") or spec.get("components", {}).get("schemas")
            if schemas:
                print("\nSchemas:")
                print(json.dumps(schemas, indent=2))
            return 0
    log.error("Could not load the API spec - open %s in a browser", config.HELPDESK_DOCS_URL)
    return 1


def list_tickets(session):
    """GET /api/tickets - show the tickets stored by the Helpdesk API."""
    url = config.HELPDESK_API_URL.rstrip("/") + config.HELPDESK_TICKET_PATH
    log.info("GET %s (Bearer token auth)", url)
    try:
        response = session.get(url, timeout=config.HTTP_TIMEOUT)
    except Exception as exc:
        log.error("Could not reach the Helpdesk API: %s", exc)
        return 1
    log.info("HTTP %s %s in %.0f ms", response.status_code, response.reason,
             response.elapsed.total_seconds() * 1000)
    try:
        print(json.dumps(response.json(), indent=2))
    except ValueError:
        print(response.text)
    return 0 if response.ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--show-api", action="store_true", help="list the Helpdesk API endpoints and exit")
    parser.add_argument("--list", action="store_true", help="list existing tickets (GET) and exit")
    parser.add_argument("--dry-run", action="store_true", help="print tickets instead of creating them")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    netlib.setup_logging(args.verbose)

    session = api_session()
    if args.show_api:
        return show_api(session)
    if args.list:
        if not config.HELPDESK_API_TOKEN:
            raise SystemExit("NETMON_API_TOKEN is not set.")
        return list_tickets(session)

    scan = netlib.read_json(config.SCAN_RESULTS_FILE)
    affected = scan["affected"]
    if not affected:
        log.info("Scan at %s found no affected devices - no tickets created", scan["scanned_at"])
        return 0
    if not args.dry_run and not config.HELPDESK_API_TOKEN:
        raise SystemExit("NETMON_API_TOKEN is not set.")

    url = config.HELPDESK_API_URL.rstrip("/") + config.HELPDESK_TICKET_PATH
    created, failed = [], []
    log.info("Helpdesk API endpoint: POST %s (Bearer token auth)", url)

    for device in affected:
        ticket = build_ticket(device, scan["scanned_at"])
        if args.dry_run:
            print(json.dumps(ticket, indent=2))
            continue
        try:
            response = session.post(url, json=ticket, timeout=config.HTTP_TIMEOUT)
        except Exception as exc:
            log.error("%-8s ticket failed: %s", device["hostname"], exc)
            failed.append(device["hostname"])
            continue

        if response.status_code in (200, 201):
            try:
                body = response.json()
                ticket_id = body.get("id") or body.get("ticket_id") or "?"
                shown = json.dumps(body, indent=2)
            except ValueError:
                ticket_id, shown = "?", response.text.strip()
            log.info("%-8s HTTP %s %s - ticket #%s created [%s, %s] in %.0f ms",
                     device["hostname"], response.status_code, response.reason, ticket_id,
                     ticket["issue_type"], ticket["priority"], response.elapsed.total_seconds() * 1000)
            print("         Response from web service:")
            print("\n".join("           " + line for line in shown.splitlines()))
            created.append(device["hostname"])
        else:
            log.error("%-8s ticket rejected: HTTP %s %s", device["hostname"],
                      response.status_code, response.text.strip()[:300])
            log.debug("%-8s payload sent:\n%s", device["hostname"], json.dumps(ticket, indent=2))
            failed.append(device["hostname"])

    if not args.dry_run:
        log.info("Tickets created: %d, failed: %d", len(created), len(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())