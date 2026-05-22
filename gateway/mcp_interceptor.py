"""
MCP Interceptor — OMNI-ANCHOR v4.3
FastAPI on :8000

AI path  (/api/fub/* /api/fello/* /api/sierra/*):
  GET        → PASS directly to CRM
  POST/PUT/PATCH → FREEZE → Telegram Apex notification → await approval
  DELETE     → HARD KILL unconditionally

Widget path (/widget/*):
  Human-initiated — direct proxy, no freeze
  Agent visibility: Glenn sees all; agents see assigned leads only

Telegram webhook (/webhook/telegram):
  Reserved for future Hermes webhook-mode relay

Freeze management:
  POST /freeze/{id}/approve  → execute stored mutation
  POST /freeze/{id}/kill     → discard

FUB inbound webhooks (/webhooks/fub):
  Receives FUB events, verifies HMAC-SHA256, routes to Telegram + ClawMem audit.
  Signature: FUB-Signature header = hmac_sha256(base64(raw_body), X-System-Key).
  Payload: {eventId, eventCreated, event, resourceIds[], uri, data{}} — no inline
  person data; handler GETs the uri to fetch full resource details.
"""

import asyncio
import base64
import hashlib
import hmac
import json
import os
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import BackgroundTasks, FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ── Config ────────────────────────────────────────────────────────────────────

DB_PATH       = os.getenv("CLAWMEM_PATH", "/root/omni-anchor/.clawmem") + "/episodic.db"
TG_TOKEN      = os.getenv("TELEGRAM_BOT_TOKEN", "")
APEX_ID       = int(os.getenv("APEX_TELEGRAM_ID", "7794812292"))
FUB_API_KEY   = os.getenv("FUB_API_KEY", "")
FUB_SYS_KEY   = os.getenv("FUB_SYS_KEY", "f1e0c6af664bc1525ecd8fecba255235")
FELLO_KEY     = os.getenv("FELLO_API_KEY", "")
SIERRA_KEY    = os.getenv("SIERRA_API_KEY", "")
GOOGLE_KEY    = os.getenv("GOOGLE_API_KEY", "")

CRM_BACKENDS = {
    "fub":    "https://api.followupboss.com/v1",
    "fello":  "https://api.fello.ai/public/v1",
    "sierra": "https://api.sierrainteractivedev.com",
}

# FUB users — for widget auth
FUB_USERS = {
    1: {"name": "Glenn Fitzgerald", "role": "broker"},
    2: {"name": "Heather Martin",   "role": "agent"},
    6: {"name": "Justin Phillips",  "role": "agent"},
    8: {"name": "Michael Arrick",   "role": "agent"},
    9: {"name": "Lloyd Gray",       "role": "agent"},
}

PASS_METHODS   = {"GET", "HEAD", "OPTIONS"}
FREEZE_METHODS = {"POST", "PUT", "PATCH"}
KILL_METHODS   = {"DELETE"}

# ── DB init ───────────────────────────────────────────────────────────────────

def db_init():
    con = sqlite3.connect(DB_PATH)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS mcp_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT NOT NULL,
            method TEXT,
            path TEXT,
            crm TEXT,
            body TEXT,
            freeze_id TEXT,
            apex_decision TEXT,
            timestamp TEXT NOT NULL,
            session_id TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_mcp_audit_ts  ON mcp_audit(timestamp);
        CREATE INDEX IF NOT EXISTS idx_mcp_audit_crm ON mcp_audit(crm);

        CREATE TABLE IF NOT EXISTS freeze_queue (
            freeze_id   TEXT PRIMARY KEY,
            method      TEXT NOT NULL,
            path        TEXT NOT NULL,
            crm         TEXT NOT NULL,
            body        TEXT,
            headers     TEXT,
            status      TEXT DEFAULT 'pending',
            created_at  TEXT NOT NULL,
            decided_at  TEXT,
            apex_decision TEXT
        );
    """)
    con.commit()
    con.close()

def audit(event, method=None, path=None, crm=None, body=None,
          freeze_id=None, apex_decision=None):
    ts = datetime.now(timezone.utc).isoformat()
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT INTO mcp_audit(event,method,path,crm,body,freeze_id,apex_decision,timestamp) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (event, method, path, crm, str(body)[:2000] if body else None,
         freeze_id, apex_decision, ts)
    )
    con.commit()
    con.close()

# ── Telegram notify ───────────────────────────────────────────────────────────

async def tg_send(text: str):
    if not TG_TOKEN:
        return
    async with httpx.AsyncClient() as c:
        await c.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": APEX_ID, "text": text, "parse_mode": "HTML"},
            timeout=8,
        )

# ── CRM auth headers ──────────────────────────────────────────────────────────

def crm_headers(crm: str) -> dict:
    if crm == "fub":
        creds = base64.b64encode(f"{FUB_API_KEY}:".encode()).decode()
        return {
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/json",
            "X-System": "OMNI-ANCHOR/1.0",
            "X-System-Key": FUB_SYS_KEY,
        }
    if crm == "fello":
        return {"x-api-key": FELLO_KEY, "Content-Type": "application/json"}
    if crm == "sierra":
        return {"Authorization": f"Bearer {SIERRA_KEY}", "Content-Type": "application/json"}
    return {}

# ── Freeze helpers ────────────────────────────────────────────────────────────

def freeze_store(freeze_id, method, path, crm, body, headers):
    ts = datetime.now(timezone.utc).isoformat()
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT INTO freeze_queue(freeze_id,method,path,crm,body,headers,status,created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (freeze_id, method, path, crm,
         json.dumps(body) if body else None,
         json.dumps(headers), "pending", ts)
    )
    con.commit()
    con.close()

def freeze_get(freeze_id: str):
    con = sqlite3.connect(DB_PATH)
    row = con.execute(
        "SELECT freeze_id,method,path,crm,body,headers,status FROM freeze_queue WHERE freeze_id=?",
        (freeze_id,)
    ).fetchone()
    con.close()
    if not row:
        return None
    return dict(zip(["freeze_id","method","path","crm","body","headers","status"], row))

def freeze_decide(freeze_id: str, decision: str):
    ts = datetime.now(timezone.utc).isoformat()
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "UPDATE freeze_queue SET status=?, apex_decision=?, decided_at=? WHERE freeze_id=?",
        (decision, decision, ts, freeze_id)
    )
    con.commit()
    con.close()

# ── App startup ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    db_init()
    await tg_send("🟢 <b>MCP Interceptor ONLINE</b>\nOMNI-ANCHOR v4.3 — :8000 ready")
    yield
    await tg_send("🔴 <b>MCP Interceptor OFFLINE</b>")

app = FastAPI(title="MCP Interceptor", version="4.3", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://widget.hvsold.com", "https://api.hvsold.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "mcp-interceptor", "version": "4.3",
            "ts": datetime.now(timezone.utc).isoformat()}

# ── Telegram webhook relay (future webhook mode) ───────────────────────────────

@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    body = await request.json()
    # Forward to Hermes gateway when webhook mode is activated
    async with httpx.AsyncClient() as c:
        try:
            await c.post("http://127.0.0.1:8900/webhook/telegram", json=body, timeout=5)
        except Exception:
            pass
    return {"ok": True}

# ── AI-path CRM proxy ─────────────────────────────────────────────────────────

@app.api_route("/api/{crm}/{path:path}", methods=["GET","POST","PUT","PATCH","DELETE"])
async def crm_proxy(crm: str, path: str, request: Request):
    if crm not in CRM_BACKENDS:
        raise HTTPException(404, f"Unknown CRM: {crm}")

    method   = request.method.upper()
    base     = CRM_BACKENDS[crm]
    full_path = f"/{path}"
    body     = None

    if method in FREEZE_METHODS or method in KILL_METHODS:
        try:
            body = await request.json()
        except Exception:
            body = None

    # HARD KILL — DELETE unconditionally blocked
    if method in KILL_METHODS:
        audit("mcp_hard_kill", method, full_path, crm, body)
        await tg_send(
            f"🚫 <b>HARD KILL BLOCKED</b>\n"
            f"CRM: {crm.upper()}\n"
            f"Op:  DELETE {full_path}\n"
            f"Status: UNCONDITIONALLY BLOCKED — logged, no escalation."
        )
        return JSONResponse(
            status_code=403,
            content={"status": "hard_kill", "detail": "DELETE operations are unconditionally blocked."}
        )

    # FREEZE — mutations queue for Apex approval
    if method in FREEZE_METHODS:
        freeze_id = uuid.uuid4().hex[:8].upper()
        headers_to_store = dict(crm_headers(crm))
        freeze_store(freeze_id, method, full_path, crm, body, headers_to_store)
        audit("mcp_freeze", method, full_path, crm, body, freeze_id=freeze_id)

        desc = _describe_mutation(crm, method, full_path, body)
        await tg_send(
            f"🔒 <b>MUTATION FROZEN #{freeze_id}</b>\n"
            f"CRM:  {crm.upper()}\n"
            f"Op:   {method} {full_path}\n"
            f"What: {desc}\n"
            f"───────────────────\n"
            f"Reply: <code>approve {freeze_id}</code> or <code>kill {freeze_id}</code>"
        )
        return JSONResponse(
            status_code=202,
            content={
                "status": "frozen",
                "freeze_id": freeze_id,
                "message": f"Mutation queued for Apex approval. Reply: approve {freeze_id} / kill {freeze_id}",
            }
        )

    # PASS — GET executes immediately
    params = dict(request.query_params)
    async with httpx.AsyncClient() as c:
        r = await c.request(
            method, f"{base}{full_path}",
            headers=crm_headers(crm), params=params, timeout=15
        )
    audit("mcp_pass", method, full_path, crm)
    return JSONResponse(status_code=r.status_code, content=r.json() if r.content else {})

# ── Freeze approval endpoints ─────────────────────────────────────────────────

@app.post("/freeze/{freeze_id}/approve")
async def freeze_approve(freeze_id: str):
    rec = freeze_get(freeze_id)
    if not rec:
        raise HTTPException(404, f"Freeze #{freeze_id} not found")
    if rec["status"] != "pending":
        raise HTTPException(409, f"Freeze #{freeze_id} already {rec['status']}")

    body    = json.loads(rec["body"]) if rec["body"] else None
    headers = json.loads(rec["headers"]) if rec["headers"] else {}
    base    = CRM_BACKENDS[rec["crm"]]

    async with httpx.AsyncClient() as c:
        r = await c.request(
            rec["method"], f"{base}{rec['path']}",
            headers=headers, json=body, timeout=15
        )

    freeze_decide(freeze_id, "approved")
    audit("mcp_approved", rec["method"], rec["path"], rec["crm"],
          freeze_id=freeze_id, apex_decision="approved")

    await tg_send(f"✅ <b>Freeze #{freeze_id} APPROVED</b> — executed {rec['method']} {rec['crm'].upper()}{rec['path']}")
    return {"status": "approved", "freeze_id": freeze_id, "crm_status": r.status_code}

@app.post("/freeze/{freeze_id}/kill")
async def freeze_kill(freeze_id: str):
    rec = freeze_get(freeze_id)
    if not rec:
        raise HTTPException(404, f"Freeze #{freeze_id} not found")
    if rec["status"] != "pending":
        raise HTTPException(409, f"Freeze #{freeze_id} already {rec['status']}")

    freeze_decide(freeze_id, "killed")
    audit("mcp_killed", rec["method"], rec["path"], rec["crm"],
          freeze_id=freeze_id, apex_decision="killed")

    await tg_send(f"🗑 <b>Freeze #{freeze_id} KILLED</b> — discarded {rec['method']} {rec['crm'].upper()}{rec['path']}")
    return {"status": "killed", "freeze_id": freeze_id}

@app.get("/freeze")
async def freeze_list():
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT freeze_id,method,path,crm,status,created_at FROM freeze_queue "
        "WHERE status='pending' ORDER BY created_at DESC LIMIT 50"
    ).fetchall()
    con.close()
    return {"pending": [dict(zip(["freeze_id","method","path","crm","status","created_at"], r)) for r in rows]}

# ── Widget API (human-path, direct proxy, agent-scoped) ───────────────────────

@app.get("/widget/leads")
async def widget_leads(agent_id: int = 0, search: str = "", limit: int = 25, offset: int = 0):
    params = {"limit": min(limit, 100), "offset": offset}
    if agent_id and agent_id != 1:
        params["assignedUserId"] = agent_id
    if search:
        params["query"] = search
    async with httpx.AsyncClient() as c:
        r = await c.get(
            f"{CRM_BACKENDS['fub']}/people",
            headers=crm_headers("fub"), params=params, timeout=15
        )
    return JSONResponse(status_code=r.status_code, content=r.json())

@app.get("/widget/leads/{person_id}")
async def widget_lead_detail(person_id: int, agent_id: int = 0):
    async with httpx.AsyncClient() as c:
        r = await c.get(
            f"{CRM_BACKENDS['fub']}/people/{person_id}",
            headers=crm_headers("fub"), timeout=15
        )
    if r.status_code != 200:
        raise HTTPException(r.status_code, "Lead not found")
    data = r.json()
    # Enforce agent scoping — agents can only view their assigned leads
    if agent_id and agent_id != 1 and data.get("assignedUserId") != agent_id:
        raise HTTPException(403, "Lead not assigned to this agent")
    return JSONResponse(content=data)

@app.get("/widget/notes")
async def widget_notes(person_id: int, limit: int = 10):
    async with httpx.AsyncClient() as c:
        r = await c.get(
            f"{CRM_BACKENDS['fub']}/notes",
            headers=crm_headers("fub"), params={"personId": person_id, "limit": min(limit, 50)}, timeout=15
        )
    return JSONResponse(status_code=r.status_code, content=r.json())

@app.post("/widget/leads/{person_id}/note")
async def widget_add_note(person_id: int, request: Request):
    body = await request.json()
    subject = body.get("subject", "Broker Note")
    note    = body.get("body", "")
    async with httpx.AsyncClient() as c:
        r = await c.post(
            f"{CRM_BACKENDS['fub']}/notes",
            headers=crm_headers("fub"),
            json={"personId": person_id, "subject": subject, "body": note, "isHtml": False},
            timeout=15
        )
    return JSONResponse(status_code=r.status_code, content=r.json() if r.content else {})

@app.post("/widget/analyze")
async def widget_analyze(
    file: UploadFile = File(None),
    prompt: str      = Form("Analyze this for real estate context"),
    context: str     = Form(""),
):
    if not GOOGLE_KEY:
        raise HTTPException(503, "GOOGLE_API_KEY not configured")
    if not file:
        raise HTTPException(400, "No file provided")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GOOGLE_KEY)
    file_bytes = await file.read()
    mime = file.content_type or "image/jpeg"

    full_prompt = prompt
    if context:
        full_prompt = f"{prompt}\n\nContext: {context}"

    response = client.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents=[
            types.Part.from_bytes(data=file_bytes, mime_type=mime),
            full_prompt,
        ]
    )
    return {"analysis": response.text}

@app.get("/widget/users")
async def widget_users():
    return {"users": [{"id": k, **v} for k, v in FUB_USERS.items()]}

# ── FUB inbound webhooks ──────────────────────────────────────────────────────
#
# FUB payload schema (no inline person data — must GET uri for details):
#   { eventId, eventCreated, event, resourceIds: [int], uri: str|null, data: {} }
#
# Signature: FUB-Signature = hmac_sha256(base64(raw_body), X-System-Key)


def _verify_fub_sig(raw_body: bytes, sig_header: str) -> bool:
    if not FUB_SYS_KEY:
        return True  # system key not yet registered — skip
    expected = hmac.new(
        FUB_SYS_KEY.encode(),
        base64.b64encode(raw_body),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, sig_header)


async def _fub_get(uri: str) -> dict:
    if not uri:
        return {}
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(uri, headers=crm_headers("fub"), timeout=10)
            return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}


def _person_display(p: dict) -> tuple:
    name   = f"{p.get('firstName', '')} {p.get('lastName', '')}".strip() or "Unknown"
    emails = p.get("emails") or []
    email  = emails[0].get("value", "—") if emails else p.get("email", "—")
    phones = p.get("phones") or []
    phone  = phones[0].get("value", "—") if phones else p.get("phone", "—")
    return name, email, phone


async def _process_fub_event(event: str, payload: dict):
    ts  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    uri = payload.get("uri")
    ids = payload.get("resourceIds", [])
    dat = payload.get("data", {})

    # Always audit
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT INTO mcp_audit(event,method,path,crm,body,timestamp) VALUES(?,?,?,?,?,?)",
        (f"fub_inbound_{event}", "WEBHOOK", "/webhooks/fub",
         "fub", json.dumps(payload)[:2000], datetime.now(timezone.utc).isoformat())
    )
    con.commit()
    con.close()

    if event == "peopleCreated":
        raw    = await _fub_get(uri)
        people = raw.get("people", [raw] if "id" in raw else [])
        for p in people[:3]:   # batch creates: notify up to 3
            name, email, phone = _person_display(p)
            assigned = FUB_USERS.get(p.get("assignedUserId", 0), {}).get("name", "Unassigned")
            source   = p.get("source", "—")
            await tg_send(
                f"🟢 <b>NEW FUB LEAD</b>\n"
                f"Name   : {name}\n"
                f"Email  : {email}\n"
                f"Phone  : {phone}\n"
                f"Source : {source}\n"
                f"Assign : {assigned}\n"
                f"ID     : {p.get('id', '?')}\n"
                f"Time   : {ts}"
            )

    elif event == "peopleStageUpdated":
        # data.stage = new stage name; fetch person for name/agent
        new_stage = dat.get("stage", "?")
        raw       = await _fub_get(uri)
        people    = raw.get("people", [raw] if "id" in raw else [])
        for p in people[:3]:
            name, _, _ = _person_display(p)
            assigned   = FUB_USERS.get(p.get("assignedUserId", 0), {}).get("name", "?")
            await tg_send(
                f"🔄 <b>FUB STAGE CHANGE</b>\n"
                f"Lead   : {name} (ID: {p.get('id', '?')})\n"
                f"Stage  : → {new_stage}\n"
                f"Agent  : {assigned}\n"
                f"Time   : {ts}"
            )

    elif event == "appointmentsCreated":
        raw  = await _fub_get(uri)
        appt = raw.get("appointments", [raw] if "id" in raw else [{}])[0]
        pid  = appt.get("personId") or (ids[0] if ids else None)
        name = "Unknown"
        if pid:
            p    = await _fub_get(f"{CRM_BACKENDS['fub']}/people/{pid}")
            name = _person_display(p)[0]
        title = appt.get("title", "—")
        start = appt.get("startTime", appt.get("start", "—"))
        agent = FUB_USERS.get(appt.get("assignedUserId", 0), {}).get("name", "?")
        await tg_send(
            f"📅 <b>FUB APPOINTMENT</b>\n"
            f"Lead   : {name}\n"
            f"Title  : {title}\n"
            f"Start  : {start}\n"
            f"Agent  : {agent}\n"
            f"Time   : {ts}"
        )

    elif event == "appointmentsUpdated":
        raw  = await _fub_get(uri)
        appt = raw.get("appointments", [raw] if "id" in raw else [{}])[0]
        pid  = appt.get("personId") or (ids[0] if ids else None)
        name = "Unknown"
        if pid:
            p    = await _fub_get(f"{CRM_BACKENDS['fub']}/people/{pid}")
            name = _person_display(p)[0]
        await tg_send(
            f"📅 <b>FUB APPT UPDATED</b>\n"
            f"Lead   : {name}\n"
            f"Title  : {appt.get('title', '—')}\n"
            f"Start  : {appt.get('startTime', appt.get('start', '—'))}\n"
            f"Time   : {ts}"
        )

    elif event == "notesCreated":
        raw  = await _fub_get(uri)
        note = raw.get("notes", [raw] if "id" in raw else [{}])[0]
        pid  = note.get("personId") or (ids[0] if ids else None)
        name = "Unknown"
        if pid:
            p    = await _fub_get(f"{CRM_BACKENDS['fub']}/people/{pid}")
            name = _person_display(p)[0]
        await tg_send(
            f"📝 <b>FUB NOTE</b>\n"
            f"Lead   : {name}\n"
            f"Subj   : {note.get('subject', '—')}\n"
            f"Body   : {str(note.get('body', '')).strip()[:140]}\n"
            f"Time   : {ts}"
        )

    elif event == "tasksCreated":
        raw  = await _fub_get(uri)
        task = raw.get("tasks", [raw] if "id" in raw else [{}])[0]
        pid  = task.get("personId") or (ids[0] if ids else None)
        name = "Unknown"
        if pid:
            p    = await _fub_get(f"{CRM_BACKENDS['fub']}/people/{pid}")
            name = _person_display(p)[0]
        agent = FUB_USERS.get(task.get("assignedUserId", 0), {}).get("name", "?")
        await tg_send(
            f"📋 <b>FUB TASK</b>\n"
            f"Lead   : {name}\n"
            f"Task   : {task.get('name', '—')}\n"
            f"Due    : {task.get('dueDate', '—')}\n"
            f"Agent  : {agent}\n"
            f"Time   : {ts}"
        )

    elif event == "dealsCreated":
        raw  = await _fub_get(uri)
        deal = raw.get("deals", [raw] if "id" in raw else [{}])[0]
        pid  = deal.get("personId") or (ids[0] if ids else None)
        name = "Unknown"
        if pid:
            p    = await _fub_get(f"{CRM_BACKENDS['fub']}/people/{pid}")
            name = _person_display(p)[0]
        await tg_send(
            f"💰 <b>FUB DEAL CREATED</b>\n"
            f"Lead   : {name}\n"
            f"Deal   : {deal.get('name', '—')}\n"
            f"Value  : {deal.get('value', '—')}\n"
            f"Stage  : {deal.get('stage', {}).get('name', '—') if isinstance(deal.get('stage'), dict) else deal.get('stage', '—')}\n"
            f"Time   : {ts}"
        )

    # peopleUpdated, peopleTagsCreated, etc. — audit only, no Telegram


@app.post("/webhooks/fub")
async def fub_webhook(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return JSONResponse({"status": "ok"})

    event = payload.get("event", payload.get("eventType", "unknown"))

    # Verify FUB-Signature if present (active once X-System-Key is registered)
    sig = request.headers.get("FUB-Signature", "")
    if sig and FUB_SYS_KEY and not _verify_fub_sig(body, sig):
        audit("fub_sig_fail", "WEBHOOK", "/webhooks/fub", "fub",
              {"event": event, "sig": sig[:20]})
        # ACK anyway — prevents FUB from auto-disabling the webhook on delivery failure
        return JSONResponse({"status": "ok", "note": "sig_mismatch_logged"})

    background_tasks.add_task(_process_fub_event, event, payload)
    return JSONResponse({"status": "ok", "event": event})


@app.get("/webhooks/fub/status")
async def fub_webhook_status():
    con    = sqlite3.connect(DB_PATH)
    recent = con.execute(
        "SELECT event, timestamp FROM mcp_audit WHERE crm='fub' AND method='WEBHOOK' "
        "ORDER BY timestamp DESC LIMIT 20"
    ).fetchall()
    con.close()
    return {
        "sys_key_configured": bool(FUB_SYS_KEY),
        "recent_events": [{"event": r[0], "ts": r[1]} for r in recent],
    }


# ── Mutation description helper ───────────────────────────────────────────────

def _describe_mutation(crm: str, method: str, path: str, body: dict) -> str:
    if not body:
        return f"{method} {path}"
    if crm == "fub":
        if "/people" in path and method == "POST":
            return f"Create lead: {body.get('firstName','')} {body.get('lastName','')} | Stage: {body.get('stageId','')}"
        if "/people" in path and method in ("PUT","PATCH"):
            return f"Update lead {path.split('/')[-1]}: {list(body.keys())}"
        if "/notes" in path:
            return f"Add note: {str(body.get('body',''))[:80]}"
        if "/tasks" in path:
            return f"Create task: {body.get('name','')} due {body.get('dueDate','')}"
        if "/events" in path:
            return f"Post event: {body.get('type','')} for person {body.get('person',{}).get('email','')}"
    if crm == "fello":
        if "/contacts" in path:
            return f"Fello contact mutation: {list(body.keys())}"
    return f"{method} {path}: {str(body)[:100]}"
