"""
FUB Webhook Registration — OMNI-ANCHOR v4.3

Registers all 8 FUB event types against https://api.hvsold.com/webhooks/fub
and persists the returned secrets to .fub_webhook_secrets.json for HMAC
verification at runtime.

PREREQUISITE — FUB requires a registered partner system to use this API:
  1. Log into followupboss.com as admin
  2. Admin → API → Integrations (or Settings → API → Connected Apps)
  3. Create integration named "OMNI-ANCHOR" with key: f1e0c6af664bc1525ecd8fecba255235
  4. Save, then re-run this script.

Usage:
  python3 fub_webhook_register.py            # register all missing events
  python3 fub_webhook_register.py --list     # list current FUB webhooks
  python3 fub_webhook_register.py --delete   # delete all OMNI-ANCHOR webhooks
"""

import argparse
import base64
import json
import sys
from pathlib import Path

import httpx

FUB_API_KEY   = "fka_0oHt627BvH4oOoy10aILIRiLBTnknLrilU"
FUB_SYS_KEY   = "f1e0c6af664bc1525ecd8fecba255235"
FUB_BASE      = "https://api.followupboss.com/v1"
WEBHOOK_URL   = "https://api.hvsold.com/webhooks/fub"
SECRETS_FILE  = Path("/root/omni-anchor/.fub_webhook_secrets.json")

# Event types — FUB uses plural resource names
EVENTS = [
    "peopleCreated",          # new lead/contact
    "peopleStageUpdated",     # stage change (data.stage = new stage name)
    "notesCreated",           # note added
    "tasksCreated",           # task created
    "appointmentsCreated",    # new appointment
    "appointmentsUpdated",    # appointment changed
    "dealsCreated",           # new deal/opportunity
    "peopleTagsCreated",      # tags added (data.tags = [])
]

_creds = base64.b64encode(f"{FUB_API_KEY}:".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {_creds}",
    "Content-Type": "application/json",
    "X-System": "OMNI-ANCHOR",
    "X-System-Key": FUB_SYS_KEY,
}


def list_webhooks() -> list:
    r = httpx.get(f"{FUB_BASE}/webhooks", headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json().get("webhooks", [])


def create_webhook(event: str) -> dict:
    r = httpx.post(f"{FUB_BASE}/webhooks", headers=HEADERS, timeout=15,
                   json={"url": WEBHOOK_URL, "event": event})
    r.raise_for_status()
    return r.json()


def delete_webhook(webhook_id: int):
    r = httpx.delete(f"{FUB_BASE}/webhooks/{webhook_id}", headers=HEADERS, timeout=15)
    if r.status_code not in (200, 204):
        print(f"  WARN: delete {webhook_id} → {r.status_code} {r.text[:80]}")


def load_secrets() -> dict:
    try:
        return json.loads(SECRETS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_secrets(secrets: dict):
    SECRETS_FILE.write_text(json.dumps(secrets, indent=2))
    print(f"  Secrets saved → {SECRETS_FILE}")


def cmd_list():
    hooks = list_webhooks()
    if not hooks:
        print("No webhooks registered.")
        return
    print(f"{'ID':<8} {'Event':<25} {'URL'}")
    for h in hooks:
        print(f"{h['id']:<8} {h.get('event','?'):<25} {h.get('url','?')}")


def cmd_register():
    existing = list_webhooks()
    registered_events = {h.get("event") for h in existing}
    secrets = load_secrets()

    for event in EVENTS:
        if event in registered_events:
            print(f"  SKIP  {event} (already registered)")
            continue
        try:
            result = create_webhook(event)
            wid    = result.get("id")
            secret = result.get("secret", "")
            secrets[event] = {"id": wid, "secret": secret}
            print(f"  OK    {event} → id={wid} secret={'set' if secret else 'none'}")
        except httpx.HTTPStatusError as e:
            print(f"  FAIL  {event} → {e.response.status_code} {e.response.text[:120]}")
            if e.response.status_code == 403:
                print()
                print("  FUB SYSTEM NOT REGISTERED. Complete the prerequisite above,")
                print("  then re-run this script.")
                sys.exit(1)

    save_secrets(secrets)
    print(f"\nRegistered {len(secrets)}/{len(EVENTS)} events.")


def cmd_delete():
    existing = list_webhooks()
    omni = [h for h in existing if h.get("url", "").startswith(WEBHOOK_URL.rsplit("/", 1)[0])]
    if not omni:
        print("No OMNI-ANCHOR webhooks found.")
        return
    for h in omni:
        delete_webhook(h["id"])
        print(f"  DELETED {h['id']} ({h.get('event','?')})")
    # Clear secrets file
    if SECRETS_FILE.exists():
        SECRETS_FILE.write_text("{}")
    print(f"Deleted {len(omni)} webhook(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FUB webhook manager")
    parser.add_argument("--list",   action="store_true", help="List current webhooks")
    parser.add_argument("--delete", action="store_true", help="Delete all OMNI-ANCHOR webhooks")
    args = parser.parse_args()

    if args.list:
        cmd_list()
    elif args.delete:
        cmd_delete()
    else:
        cmd_register()
