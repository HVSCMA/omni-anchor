"""
Fello API Client — OMNI-ANCHOR v4.3
Base URL   : https://api.fello.ai
Auth       : x-api-key header
Rate limits: GET 100/10s | WRITE 50/10s | 350,000/day
"""
import httpx, hmac, hashlib, json, asyncio
from typing import Optional
from dataclasses import dataclass

FELLO_BASE = "https://api.fello.ai/public/v1"
FELLO_API_KEY = "uiQ4jADoUGeTqaBellkEcBxxrzQvgvnj"
FELLO_SECRET  = "S4Cqm/OCgF7lKafKSNXX0gkdXMuDQbdu"

HEADERS = {"x-api-key": FELLO_API_KEY, "Content-Type": "application/json"}

# ── Rate limit state ────────────────────────────────────────────────────────
import time
_window_start = time.time()
_window_get_count = 0
_window_write_count = 0

async def _rate_guard(method: str):
    global _window_start, _window_get_count, _window_write_count
    now = time.time()
    if now - _window_start > 10:
        _window_start = now
        _window_get_count = 0
        _window_write_count = 0
    if method == "GET":
        if _window_get_count >= 95:
            await asyncio.sleep(10 - (now - _window_start) + 0.1)
        _window_get_count += 1
    else:
        if _window_write_count >= 45:
            await asyncio.sleep(10 - (now - _window_start) + 0.1)
        _window_write_count += 1

# ── Webhook signature verification ─────────────────────────────────────────
def verify_webhook(payload: bytes, signature_header: str) -> bool:
    expected = hmac.new(
        FELLO_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)

# ─────────────────────────────────────────────────────────────────────────────
# CONTACTS
# ─────────────────────────────────────────────────────────────────────────────

async def get_contact(contact_id: str = None, email_id: str = None) -> dict:
    """GET /contact — by contactId or emailId"""
    await _rate_guard("GET")
    params = {}
    if contact_id: params["contactId"] = contact_id
    if email_id:   params["emailId"] = email_id
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{FELLO_BASE}/contact", headers=HEADERS, params=params)
    return _handle(r)

async def add_contact(
    email: str,
    name: str = None,
    phone: str = None,
    tags: list[str] = None,
    address: str = None,
    crm_fields: dict = None,
    assigned_user_email: str = None
) -> dict:
    """POST /contact — create contact. Email required."""
    await _rate_guard("POST")
    body = {"email": email}
    if name:                body["name"] = name[:64]
    if phone:               body["phone"] = phone[:32]
    if tags:                body["tags"] = [t[:32] for t in tags]
    if address:             body["address"] = address[:256]
    if crm_fields:          body["crmFields"] = crm_fields
    if assigned_user_email: body["assignedUserEmailId"] = assigned_user_email
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{FELLO_BASE}/contact", headers=HEADERS, json=body)
    return _handle(r)

async def update_contact(contact_id: str, **kwargs) -> dict:
    """PATCH /contact/{contactId} — partial update, only supplied fields change."""
    await _rate_guard("PATCH")
    allowed = {"name", "phone", "email", "assignedUserEmailId", "recordStatus", "crmFields"}
    body = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    async with httpx.AsyncClient() as c:
        r = await c.patch(f"{FELLO_BASE}/contact/{contact_id}", headers=HEADERS, json=body)
    return _handle(r)

async def delete_contact(contact_id: str) -> bool:
    """DELETE /contact/{contactId} — HARD KILL path, always requires Apex approval."""
    await _rate_guard("DELETE")
    async with httpx.AsyncClient() as c:
        r = await c.delete(f"{FELLO_BASE}/contact/{contact_id}", headers=HEADERS)
    return r.status_code == 204

# ─────────────────────────────────────────────────────────────────────────────
# TAGS
# ─────────────────────────────────────────────────────────────────────────────

async def add_tags(contact_id: str, tags: list[str]) -> dict:
    await _rate_guard("POST")
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{FELLO_BASE}/contact/{contact_id}/tags",
                         headers=HEADERS, json={"tags": tags})
    return _handle(r)

async def replace_tags(contact_id: str, tags: list[str]) -> dict:
    await _rate_guard("PUT")
    async with httpx.AsyncClient() as c:
        r = await c.put(f"{FELLO_BASE}/contact/{contact_id}/tags",
                        headers=HEADERS, json={"tags": tags})
    return _handle(r)

async def remove_tags(contact_id: str, tags: list[str]) -> dict:
    await _rate_guard("DELETE")
    async with httpx.AsyncClient() as c:
        r = await c.delete(f"{FELLO_BASE}/contact/{contact_id}/tags",
                           headers=HEADERS, json={"tags": tags})
    return _handle(r)

# ─────────────────────────────────────────────────────────────────────────────
# PROPERTIES
# ─────────────────────────────────────────────────────────────────────────────

async def add_property(contact_id: str, address: str) -> dict:
    """Add a property to a contact. Address string validated by Fello."""
    await _rate_guard("POST")
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{FELLO_BASE}/contact/{contact_id}/property",
                         headers=HEADERS, json={"address": address})
    return _handle(r)

async def archive_property(property_id: str) -> bool:
    """Archive (soft-delete) a property. Requires Apex approval per MCP rules."""
    await _rate_guard("POST")
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{FELLO_BASE}/contact/property/{property_id}/archive",
                         headers=HEADERS)
    return r.status_code == 204

# ─────────────────────────────────────────────────────────────────────────────
# WEBHOOKS
# ─────────────────────────────────────────────────────────────────────────────

WEBHOOK_EVENTS = [
    "FormSubmission", "ContactEnriched", "DashboardClick", "EmailClick",
    "PostcardScan", "ContactUnsubscribed", "ContactDetailsUpdated",
    "TagsAdded", "TagsRemoved"
]

async def list_webhooks() -> list:
    await _rate_guard("GET")
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{FELLO_BASE}/webhooks", headers=HEADERS)
    return _handle(r)

async def register_webhook(url: str, event_type: str) -> dict:
    """Register a webhook. Max 3 per event type."""
    if event_type not in WEBHOOK_EVENTS:
        raise ValueError(f"Invalid eventType. Must be one of: {WEBHOOK_EVENTS}")
    await _rate_guard("POST")
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{FELLO_BASE}/webhooks", headers=HEADERS,
                         json={"url": url[:256], "eventType": event_type})
    return _handle(r)

async def remove_webhook(subscription_id: str) -> bool:
    await _rate_guard("DELETE")
    async with httpx.AsyncClient() as c:
        r = await c.delete(f"{FELLO_BASE}/webhooks/{subscription_id}", headers=HEADERS)
    return r.status_code == 204

# ─────────────────────────────────────────────────────────────────────────────
# ERROR HANDLING
# ─────────────────────────────────────────────────────────────────────────────

ERROR_MAP = {
    "ContactDoesNotExist": "Contact not found",
    "PropertyDoesNotExist": "Property not found",
    "InvalidAddress": "Address validation failed",
    "DuplicateProperty": "Duplicate address on this contact",
    "DuplicateContact": "Contact with this email already exists",
    "InvalidRequest": "JSON validation error",
}

def _handle(r: httpx.Response) -> dict:
    if r.status_code in (200, 201):
        return r.json()
    if r.status_code == 204:
        return {"status": "success"}
    try:
        err = r.json()
        code = err.get("code", "Unknown")
        msg = ERROR_MAP.get(code, err.get("message", "Unknown error"))
        raise FelloAPIError(code=code, message=msg, status=r.status_code, raw=err)
    except (ValueError, KeyError):
        raise FelloAPIError(code="ParseError", message=r.text, status=r.status_code)

class FelloAPIError(Exception):
    def __init__(self, code, message, status, raw=None):
        self.code = code
        self.message = message
        self.status = status
        self.raw = raw
        super().__init__(f"[{status}] {code}: {message}")
