"""
Follow Up Boss API Client — OMNI-ANCHOR v4.3
Base URL  : https://api.followupboss.com/v1
Auth      : Basic (API_KEY:) — key as username, blank password
Rate limit: 250 global / 10s | 25 PUT.people / 10s | 10 notes / 10s
Pagination: offset+limit (max 100) or cursor via _metadata.next
"""
import httpx, base64, asyncio, json, time
from typing import Optional

FUB_API_KEY    = "fka_0oHt627BvH4oOoy10aILIRiLBTnknLrilU"
FUB_BASE       = "https://api.followupboss.com/v1"
FUB_SYS_KEY    = "f1e0c6af664bc1525ecd8fecba255235"

_creds = base64.b64encode(f"{FUB_API_KEY}:".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {_creds}",
    "Content-Type": "application/json",
    "X-System": "OMNI-ANCHOR/1.0",
    "X-System-Key": FUB_SYS_KEY,
}

# ── Live schema (verified 2026-05-20) ────────────────────────────────────────

STAGES = {
    2:  "Lead",          12: "Hot Prospect",  13: "Nurture",
    17: "Active Client", 14: "Pending",        8: "Closed",
    15: "Past Client",   16: "Sphere",        11: "Trash",
    18: "Unresponsive",
}

PIPELINE_STAGES = {
    "Sellers": {
        30: "New Opp.- Build CMA", 31: "CMA Built", 28: "CMA Sent / Need Appt",
        29: "Appt. Completed",     20: "Listed",     22: "Offer",
        24: "Pending",             26: "Closed",
    },
    "Buyers": {
        19: "Buyer Contract", 21: "Offer", 23: "Pending", 25: "Closed",
    },
    "New Fello": {32: "New Opp.- Build CMA"},
}

PIPELINE_IDS = {"Sellers": 2, "Buyers": 1, "New Fello": 3}

USERS = {
    1: {"name": "Glenn Fitzgerald", "role": "Broker",  "email": "glenn@hudsonvalleysold.com"},
    2: {"name": "Heather Martin",   "role": "Agent",   "email": "heatherdaddezio@gmail.com"},
    6: {"name": "Justin Phillips",  "role": "Agent",   "email": "dutchessbroker@gmail.com"},
    8: {"name": "Michael Arrick",   "role": "Agent",   "email": "Mikesoldarrick@gmail.com"},
    9: {"name": "Lloyd Gray",       "role": "Agent",   "email": "lbom8@aol.com"},
}

SPOKE_USER_MAP = {"heather": 2, "alpha": 1, "beta": 1, "gamma": 1}

CUSTOM_FIELDS = {
    "customOmniTriggerTimestamp": 186,
    "customOmniTriggerReason":    185,
    "customOmniRelevancyTier":    184,
    "customWILLOWMargin":         183,
    "customWILLOWValuation":      182,
    "customRealScoutContactState":   181,
    "customRealScoutScoutScore":     180,
    "customRealScoutHomeValueAlertViewsCount": 179,
    "customRealScoutMarketAlertViewsCount":    178,
    "customRealScoutPropertyViewsCount":       177,
}

# ── Rate guard ────────────────────────────────────────────────────────────────

_rl = {"window": time.time(), "global": 0, "put_people": 0, "notes": 0}

async def _guard(ctx: str = "global"):
    now = time.time()
    if now - _rl["window"] > 10:
        _rl.update({"window": now, "global": 0, "put_people": 0, "notes": 0})
    limits = {"global": 240, "put_people": 24, "notes": 9}
    if _rl.get(ctx, 0) >= limits.get(ctx, 240):
        await asyncio.sleep(10 - (now - _rl["window"]) + 0.1)
    _rl["global"] = _rl.get("global", 0) + 1
    _rl[ctx] = _rl.get(ctx, 0) + 1

# ── Core request ──────────────────────────────────────────────────────────────

async def _req(method: str, path: str, rl_ctx="global", **kwargs) -> dict:
    await _guard(rl_ctx)
    async with httpx.AsyncClient() as c:
        r = await c.request(method, f"{FUB_BASE}{path}", headers=HEADERS, timeout=15, **kwargs)
    if r.status_code == 429:
        retry = int(r.headers.get("Retry-After", 5))
        await asyncio.sleep(retry)
        return await _req(method, path, rl_ctx, **kwargs)
    if r.status_code in (200, 201):
        return r.json() if r.content else {}
    if r.status_code == 204:
        return {"status": "deleted"}
    raise FUBError(r.status_code, r.text)

# ── Pagination helper ─────────────────────────────────────────────────────────

async def paginate(path: str, collection_key: str, params: dict = None) -> list:
    results, cursor = [], None
    params = dict(params or {})
    params["limit"] = 100
    while True:
        if cursor:
            params["next"] = cursor
        data = await _req("GET", path, params=params)
        results.extend(data.get(collection_key, []))
        meta = data.get("_metadata", {})
        cursor = meta.get("next")
        if not cursor or len(data.get(collection_key, [])) == 0:
            break
    return results

# ─────────────────────────────────────────────────────────────────────────────
# PEOPLE (Contacts / Leads)
# ─────────────────────────────────────────────────────────────────────────────

async def get_people(limit=10, offset=0, stage_id=None, assigned_user_id=None,
                     query=None, tags=None) -> dict:
    params = {"limit": min(limit, 100), "offset": offset}
    if stage_id:          params["stageId"] = stage_id
    if assigned_user_id:  params["assignedUserId"] = assigned_user_id
    if query:             params["query"] = query
    if tags:              params["tags"] = tags
    return await _req("GET", "/people", params=params)

async def get_person(person_id: int) -> dict:
    return await _req("GET", f"/people/{person_id}")

async def get_person_by_email(email: str) -> Optional[dict]:
    data = await _req("GET", "/people", params={"query": email, "limit": 1})
    people = data.get("people", [])
    return people[0] if people else None

async def create_person(
    first_name: str, last_name: str,
    emails: list[dict] = None,    # [{"value": "x@y.com", "type": "work"}]
    phones: list[dict] = None,    # [{"value": "8455551234", "type": "mobile"}]
    stage_id: int = 2,            # default: Lead
    assigned_user_id: int = 1,    # default: Glenn
    source: str = None,
    tags: list[str] = None,
    custom_fields: dict = None,   # {"customWILLOWValuation": 485000}
    pipeline_id: int = None,
    pipeline_stage_id: int = None,
) -> dict:
    body = {
        "firstName": first_name,
        "lastName":  last_name,
        "stageId":   stage_id,
        "assignedUserId": assigned_user_id,
    }
    if emails:             body["emails"]  = emails
    if phones:             body["phones"]  = phones
    if source:             body["source"]  = source
    if tags:               body["tags"]    = tags
    if custom_fields:      body.update(custom_fields)
    if pipeline_id:        body["pipelineId"] = pipeline_id
    if pipeline_stage_id:  body["pipelineStageId"] = pipeline_stage_id
    return await _req("POST", "/people", json=body)

async def update_person(person_id: int, **kwargs) -> dict:
    return await _req("PUT", f"/people/{person_id}", json=kwargs, rl_ctx="put_people")

async def update_stage(person_id: int, stage_id: int) -> dict:
    if stage_id not in STAGES:
        raise ValueError(f"Invalid stage_id {stage_id}. Valid: {STAGES}")
    return await _req("PUT", f"/people/{person_id}", json={"stageId": stage_id}, rl_ctx="put_people")

async def add_tags(person_id: int, tags: list[str]) -> dict:
    person = await get_person(person_id)
    existing = person.get("tags", [])
    merged = list(set(existing + tags))
    return await _req("PUT", f"/people/{person_id}", json={"tags": merged}, rl_ctx="put_people")

async def remove_tags(person_id: int, tags: list[str]) -> dict:
    person = await get_person(person_id)
    remaining = [t for t in person.get("tags", []) if t not in tags]
    return await _req("PUT", f"/people/{person_id}", json={"tags": remaining}, rl_ctx="put_people")

# ─────────────────────────────────────────────────────────────────────────────
# EVENTS (lead intake / activity logging)
# ─────────────────────────────────────────────────────────────────────────────

async def post_event(
    type: str,              # "Registration", "Inquiry", "Property Inquiry", etc.
    person: dict,           # {"email": "x@y.com", "firstName": "...", "lastName": "..."}
    source: str = "OMNI-ANCHOR",
    source_url: str = None,
    property_address: str = None,
    property_price: int = None,
    message: str = None,
) -> dict:
    body = {"type": type, "person": person, "source": source}
    if source_url:        body["sourceUrl"] = source_url
    if message:           body["message"] = message
    if property_address:
        body["property"] = {"address": property_address}
        if property_price:
            body["property"]["price"] = property_price
    return await _req("POST", "/events", json=body)

# ─────────────────────────────────────────────────────────────────────────────
# NOTES
# ─────────────────────────────────────────────────────────────────────────────

async def create_note(person_id: int, subject: str, body: str, is_html=False) -> dict:
    return await _req("POST", "/notes", rl_ctx="notes", json={
        "personId": person_id, "subject": subject,
        "body": body, "isHtml": is_html,
    })

async def get_notes(person_id: int) -> list:
    return await paginate(f"/notes", "notes", {"personId": person_id})

# ─────────────────────────────────────────────────────────────────────────────
# TASKS
# ─────────────────────────────────────────────────────────────────────────────

TASK_TYPES = ["Call", "Email", "Text", "Appointment", "To-Do", "Other"]

async def create_task(
    person_id: int,
    name: str,
    due_date: str,          # ISO 8601 UTC
    type: str = "Call",
    assigned_user_id: int = 1,
) -> dict:
    if type not in TASK_TYPES:
        raise ValueError(f"Task type must be one of: {TASK_TYPES}")
    return await _req("POST", "/tasks", json={
        "personId": person_id, "name": name,
        "dueDate": due_date, "type": type,
        "assignedUserId": assigned_user_id,
    })

async def complete_task(task_id: int) -> dict:
    return await _req("PUT", f"/tasks/{task_id}", json={"isCompleted": True})

# ─────────────────────────────────────────────────────────────────────────────
# WEBHOOKS
# ─────────────────────────────────────────────────────────────────────────────

async def list_webhooks() -> list:
    data = await _req("GET", "/webhooks")
    return data.get("webhooks", [])

async def create_webhook(url: str, event: str) -> dict:
    return await _req("POST", "/webhooks", json={"url": url, "event": event})

async def delete_webhook(webhook_id: int) -> dict:
    return await _req("DELETE", f"/webhooks/{webhook_id}")

# ─────────────────────────────────────────────────────────────────────────────
# DEALS / PIPELINES
# ─────────────────────────────────────────────────────────────────────────────

async def move_to_pipeline(person_id: int, pipeline: str, stage_name: str) -> dict:
    pid = PIPELINE_IDS.get(pipeline)
    if not pid:
        raise ValueError(f"Pipeline must be: {list(PIPELINE_IDS)}")
    stages = PIPELINE_STAGES.get(pipeline, {})
    sid = next((k for k, v in stages.items() if v == stage_name), None)
    if not sid:
        raise ValueError(f"Stage '{stage_name}' not in {pipeline}. Valid: {list(stages.values())}")
    return await _req("PUT", f"/people/{person_id}", rl_ctx="put_people",
                      json={"pipelineId": pid, "pipelineStageId": sid})

# ─────────────────────────────────────────────────────────────────────────────
# SEARCH / SMART LISTS
# ─────────────────────────────────────────────────────────────────────────────

async def search_people(query: str, limit=10) -> list:
    data = await _req("GET", "/people", params={"query": query, "limit": limit})
    return data.get("people", [])

async def get_smart_lists() -> list:
    data = await _req("GET", "/smartLists")
    return data.get("smartlists", [])

# ─────────────────────────────────────────────────────────────────────────────
# ERROR HANDLING
# ─────────────────────────────────────────────────────────────────────────────

class FUBError(Exception):
    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__(f"[{status}] FUB API Error: {body[:200]}")
