"""Send a TRISA transfer from counterparty.local (stand-in for an external
developer's wallet/CASP) to envoy.local (this container's TRISA node), to
demonstrate the sanctions-screening entry point end to end.

This is the direction that matters for the demo: compliance.local's webhook
is wired to envoy.local, and Envoy only calls its webhook for transfers it
*receives* -- so the transfer must originate from the counterparty, not from
envoy.local itself (cmd/fsi's built-in `tests:trisa` sends the other way,
which never touches our webhook).

Usage:
    python send_transfer.py --clean
    python send_transfer.py --flagged

Credentials: reads counterparty.local's API client id/secret from
envoy/tmp/creds/counterparty_local_apikey.txt (created by
`envoy createapikey all` inside the counterparty.local container -- see
scripts/bootstrap.ps1), or from COUNTERPARTY_CLIENT_ID / COUNTERPARTY_SECRET
env vars if set.
"""

import argparse
import os
import random
import sqlite3
import sys
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
CREDS_FILE = REPO_ROOT / "envoy" / "tmp" / "creds" / "counterparty_local_apikey.txt"
SANCTIONS_DB = REPO_ROOT / "compliance-service" / "tmp" / "data" / "compliance.db"

COUNTERPARTY_ENDPOINT = "http://localhost:9000"


def _read_creds():
    client_id = os.environ.get("COUNTERPARTY_CLIENT_ID")
    secret = os.environ.get("COUNTERPARTY_SECRET")
    if client_id and secret:
        return client_id, secret

    if not CREDS_FILE.exists():
        raise SystemExit(
            f"no credentials found: set COUNTERPARTY_CLIENT_ID/COUNTERPARTY_SECRET "
            f"or run scripts/bootstrap.ps1 to create {CREDS_FILE}"
        )

    client_id = secret = None
    for line in CREDS_FILE.read_text().splitlines():
        if line.startswith("client id:"):
            client_id = line.split("\t", 1)[1].strip()
        elif line.startswith("client secret:"):
            secret = line.split("\t", 1)[1].strip()
    if not client_id or not secret:
        raise SystemExit(f"could not parse credentials from {CREDS_FILE}")
    return client_id, secret


def _authenticate(client_id: str, secret: str) -> str:
    resp = requests.post(
        f"{COUNTERPARTY_ENDPOINT}/v1/authenticate",
        json={"client_id": client_id, "client_secret": secret},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _find_envoy_travel_address(token: str) -> str:
    resp = requests.get(
        f"{COUNTERPARTY_ENDPOINT}/v1/counterparties",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    counterparties = resp.json().get("counterparties") or []
    for cp in counterparties:
        if "envoy.local" in (cp.get("endpoint") or "").lower():
            travel_address = cp.get("travel_address")
            if travel_address:
                return travel_address
    raise SystemExit(
        "could not find envoy.local's travel address in counterparty.local's "
        "directory sync -- has `go run ./cmd/fsi gds:init` been run, and has "
        "envoy.local/counterparty.local been restarted since?"
    )


def _clean_person(role: str) -> dict:
    if role == "originator":
        return {
            "crypto_address": "n2XftYsk9EvsjdgFbKjd96qu4aXL3pSBu2",
            "forename": "Fearne",
            "surname": "Duncan",
            "country_of_residence": "US",
            "customer_id": "demo-clean-originator",
            "addresses": [{"address_type": "GEOG", "address_lines": ["1 Example St"], "country": "US"}],
        }
    return {
        "crypto_address": "n3oDpHRYue9Ene9neasSE9cchfXNdtfzYM",
        "forename": "Alice",
        "surname": "Murray",
        "country_of_residence": "US",
        "customer_id": "demo-clean-beneficiary",
        "addresses": [{"address_type": "GEOG", "address_lines": ["2 Example Ave"], "country": "US"}],
    }


def _pick_sanctioned_name() -> str:
    if not SANCTIONS_DB.exists():
        raise SystemExit(
            f"sanctions database not found at {SANCTIONS_DB} -- run the "
            f"compliance-service sanctions ingest first (see compliance-service README)"
        )

    conn = sqlite3.connect(str(SANCTIONS_DB))
    try:
        rows = conn.execute(
            "SELECT primary_name FROM sanctioned_entities WHERE entity_type = 'person' AND is_active = 1"
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        raise SystemExit("no active sanctioned 'person' entities found in the ingested list")

    name = random.choice(rows)[0]
    print(f"[flagged demo] using sanctioned-list name: {name!r}", file=sys.stderr)
    return name


def _flagged_person(role: str, sanctioned_name: str) -> dict:
    if role != "originator":
        return _clean_person("beneficiary")

    parts = sanctioned_name.split()
    forename, surname = (parts[0], " ".join(parts[1:])) if len(parts) > 1 else (sanctioned_name, sanctioned_name)
    return {
        "crypto_address": "n2XftYsk9EvsjdgFbKjd96qu4aXL3pSBu2",
        "forename": forename,
        "surname": surname,
        "country_of_residence": "US",
        "customer_id": "demo-flagged-originator",
        "addresses": [{"address_type": "GEOG", "address_lines": ["1 Example St"], "country": "US"}],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--clean", action="store_true", help="clean synthetic names -> expect accepted")
    mode.add_argument("--flagged", action="store_true", help="a real sanctions-list name -> expect review/rejected")
    args = parser.parse_args()

    client_id, secret = _read_creds()
    token = _authenticate(client_id, secret)
    travel_address = _find_envoy_travel_address(token)

    if args.flagged:
        sanctioned_name = _pick_sanctioned_name()
        originator = _flagged_person("originator", sanctioned_name)
        beneficiary = _flagged_person("beneficiary", sanctioned_name)
    else:
        originator = _clean_person("originator")
        beneficiary = _clean_person("beneficiary")

    prepare_payload = {
        "routing": {"protocol": "trisa", "travel_address": travel_address},
        "originator": originator,
        "beneficiary": beneficiary,
        "transfer": {"amount": 0.05, "network": "BTC", "asset_type": "BTC"},
    }

    resp = requests.post(
        f"{COUNTERPARTY_ENDPOINT}/v1/transactions/prepare",
        json=prepare_payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    prepared = resp.json()

    resp = requests.post(
        f"{COUNTERPARTY_ENDPOINT}/v1/transactions/send-prepared",
        json=prepared,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    transaction = resp.json()

    print(f"transaction sent: {transaction.get('id')}")
    print("check the compliance officer UI at http://localhost:8300/review/ for the decision")


if __name__ == "__main__":
    main()
