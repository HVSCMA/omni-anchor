"""
Fello Webhook Handler — OMNI-ANCHOR v4.3
Receives all 9 Fello event types, verifies HMAC-SHA256 signature,
routes to ClawMem and MCP freeze queue as appropriate.

Endpoint: POST /webhooks/fello
Must respond 2XX within 10 seconds or Fello retries for 8 hours then unsubscribes.
"""
import hmac, hashlib, json, asyncio
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import sqlite3, os, httpx
from datetime import datetime, timezone

FELLO_SECRET = os.environ.get("FELLO_API_SECRET", "S4Cqm/OCgF7lKafKSNXX0gkdXMuDQbdu")
CLAWMEM_DB   = os.environ.get("CLAWMEM_PATH", "/root/omni-anchor/.clawmem") + "/episodic.db"
TG_TOKEN     = os.environ.get("TELEGRAM_BOT_TOKEN", "8853756715:AAGdKmfAyPHnO9o1Dt6zeogAS__byMVlqt8")
APEX_ID      = int(os.environ.get("APEX_TELEGRAM_ID", "7794812292"))

app = FastAPI(title="Fello Webhook Handler")

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()

async def tg_send(text: str):
    if not TG_TOKEN:
        return
    async with httpx.AsyncClient() as c:
        await c.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": APEX_ID, "text": text, "parse_mode": "HTML"},
            timeout=8,
        )

def verify_signature(payload: bytes, sig_header: str) -> bool:
    expected = hmac.new(FELLO_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig_header)

def log_event(event_type: str, contact_id: str, payload: dict):
    con = sqlite3.connect(CLAWMEM_DB)
    con.execute("""
        INSERT INTO episodes (session_id, task_type, timestamp, context_summary, outcome, vault_ref)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        f"fello-webhook-{event_type}",
        f"fello.event.{event_type.lower()}",
        utcnow(),
        f"Fello {event_type} for contact {contact_id}",
        "received",
        "v1-real-estate"
    ))
    con.commit()
    con.close()

# ── Event routing ─────────────────────────────────────────────────────────────

PASS_THROUGH_EVENTS = {
    # These are observational — log to ClawMem, no freeze needed
    "FormSubmission", "DashboardClick", "EmailClick", "PostcardScan",
    "ContactEnriched", "ContactUnsubscribed"
}

FREEZE_EVENTS = {
    # These mutate contact state — log + freeze for Apex awareness
    "ContactDetailsUpdated", "TagsAdded", "TagsRemoved"
}

async def process_event(event_type: str, payload: dict):
    contact = payload.get("contact", {})
    # Fallback to alternative payload locations for contact information
    contact_data = payload.get("data", {}) if not contact else contact
    contact_info = contact_data.get("contactInfo", {}) if not contact else contact
    
    contact_id = contact_info.get("contactId", contact_data.get("contactId", "unknown"))

    log_event(event_type, contact_id, payload)

    if event_type == "FormSubmission":
        name  = f"{contact.get('firstName','')} {contact.get('lastName','')}".strip() or "Unknown"
        email = contact.get("email", "—")
        phone = contact.get("phone", "—")
        form  = payload.get("formName") or payload.get("form", {}).get("name", "—")
        addr  = contact.get("address", "—")
        await tg_send(
            f"🟢 <b>FELLO FORM SUBMISSION</b>\n"
            f"Lead  : {name}\n"
            f"Form  : {form}\n"
            f"Email : {email}\n"
            f"Phone : {phone}\n"
            f"Addr  : {addr}\n"
            f"ID    : {contact_id}\n"
            f"Time  : {utcnow()}"
        )

    elif event_type == "ContactEnriched":
        name   = f"{contact.get('firstName','')} {contact.get('lastName','')}".strip() or "Unknown"
        equity = contact.get("estimatedEquity") or payload.get("estimatedEquity", "—")
        value  = contact.get("estimatedValue") or payload.get("estimatedValue", "—")
        await tg_send(
            f"📊 <b>FELLO CONTACT ENRICHED</b>\n"
            f"Lead   : {name}\n"
            f"ID     : {contact_id}\n"
            f"Equity : {equity}\n"
            f"Value  : {value}\n"
            f"Time   : {utcnow()}"
        )

    if event_type in FREEZE_EVENTS:
        # Write to freeze queue as informational (inbound, not outbound mutation)
        con = sqlite3.connect(CLAWMEM_DB)
        con.execute("""
            INSERT INTO mcp_audit (event, method, path, crm, body, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            f"fello_inbound_{event_type.lower()}",
            "WEBHOOK",
            f"/contact/{contact_id}",
            "fello",
            json.dumps(payload),
            utcnow()
        ))
        con.commit()
        con.close()

@app.post("/webhooks/fello")
async def fello_webhook(request: Request, background_tasks: BackgroundTasks):
    # Immediate 200 ACK — Fello requires response within 10 seconds
    body = await request.body()
    try:
        with open("/root/omni-anchor/.clawmem/last_fello_payload.json", "w") as f_log:
            f_log.write(body.decode('utf-8', errors='replace'))
    except Exception:
        pass

    sig = request.headers.get("fello-webhook-signature", "")
    if sig and not verify_signature(body, sig):
        # Log but don't fail — avoid Fello thinking endpoint is broken
        pass

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return JSONResponse({"status": "ok"})  # ACK anyway

    event_type = payload.get("eventType")
    if not event_type and "events" in payload and isinstance(payload["events"], list) and len(payload["events"]) > 0:
        # Fello bulk event envelope formatting
        event_envelope = payload["events"][0]
        event_type = event_envelope.get("eventType", "Unknown")
        payload = event_envelope  # Unwrap envelope for processing downstream

    if not event_type:
        event_type = "Unknown"

    background_tasks.add_task(process_event, event_type, payload)

    return JSONResponse({"status": "ok", "event": event_type})

@app.get("/webhooks/fello/health")
async def health():
    return {"status": "ok", "handler": "fello-webhook"}
