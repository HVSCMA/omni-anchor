# FILE 12: MCP INTERCEPTOR
## Model Context Protocol Background Watcher — KVM4 ↔ CRM Bridge

---

## SECTION 1: INTERCEPTOR ROLE

The MCP Interceptor runs as a persistent background process on KVM4. It sits between Hermes and all CRM API clients (FUB, Sierra, Fello) and enforces the mutation freeze rules defined in Files 13-15. Every API call is logged, classified, and either passed or frozen.

---

## SECTION 2: INTERCEPTOR ARCHITECTURE

```
Hermes Core
    |
    | (MCP tool call)
    v
MCP Interceptor (background watcher)
    |
    +-- classify_operation(method, endpoint)
    |        |
    |        +-- GET/QUERY  → PASS → CRM API
    |        +-- POST/PUT/PATCH → FREEZE → Apex Queue
    |        +-- DELETE → HARD KILL (no Apex escalation)
    |
    v
Audit Log (SQLite)
```

---

## SECTION 3: INTERCEPTOR SERVER

```python
from fastapi import FastAPI, Request, HTTPException
import httpx
import asyncio

app = FastAPI()

MUTATION_METHODS = {"POST", "PUT", "PATCH"}
KILL_METHODS = {"DELETE"}

@app.middleware("http")
async def mcp_intercept(request: Request, call_next):
    method = request.method.upper()
    path = request.url.path
    crm = classify_crm_from_path(path)

    if method in KILL_METHODS:
        await audit_log.write({
            "event": "mcp_hard_kill",
            "method": method,
            "path": path,
            "crm": crm,
            "timestamp": utcnow()
        })
        raise HTTPException(status_code=403, detail="DELETE operations are unconditionally blocked.")

    if method in MUTATION_METHODS:
        body = await request.body()
        freeze_id = await freeze_queue.enqueue({
            "method": method,
            "path": path,
            "crm": crm,
            "body": body.decode(),
            "timestamp": utcnow(),
            "status": "pending_apex_approval"
        })
        await notify_apex(f"Frozen mutation #{freeze_id}: {method} {crm}{path}")
        return JSONResponse({"status": "frozen", "freeze_id": freeze_id,
                             "message": "Mutation queued for Apex approval."})

    # GET passes through
    response = await call_next(request)
    return response
```

---

## SECTION 4: APEX APPROVAL FLOW

```
Apex receives Telegram notification: "Frozen mutation #42: POST FUB /leads"
Apex responds: "approve 42" or "kill 42"
    |
    v
Hermes parses Apex command
    |
    +-- approve → execute original mutation against CRM API
    +-- kill    → delete from freeze queue, log, notify requester
```

---

## SECTION 5: AUDIT TRAIL SCHEMA

```sql
CREATE TABLE mcp_audit (
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
CREATE INDEX idx_mcp_audit_timestamp ON mcp_audit(timestamp);
CREATE INDEX idx_mcp_audit_crm ON mcp_audit(crm);
```
