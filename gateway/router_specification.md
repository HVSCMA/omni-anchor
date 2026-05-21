# FILE 03: ROUTER SPECIFICATION
## Omni-Gateway Switchboard — Telegram Decoupling & Human Topology Validation

---

## SECTION 1: ARCHITECTURE OVERVIEW

```
Inbound channels:
  Telegram  --> nginx :443 --> Redis queue --> GatewayRouter
  CLI       ----------------------------------------^
  Slack/Discord (future)

GatewayRouter outputs to:
  IntentClassifier (File 04)
  HumanTopology validator
  Audit log (SQLite)
```

---

## SECTION 2: TELEGRAM INSTANT DECOUPLING

2.1 The router's first action on any Telegram payload is to ACK the webhook with HTTP 200 before processing.
2.2 Processing happens asynchronously. Telegram never waits on Hermes.

```python
@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    payload = await request.json()
    await redis.lpush("telegram:inbound", json.dumps(payload))
    return {"ok": True}  # instant ACK — never block here
```

---

## SECTION 3: HUMAN TOPOLOGY VALIDATION

3.1 Every inbound message must carry an identity token (Telegram user_id, CLI session token, etc.).
3.2 The router validates this token against the Human Network registry (File 19) before any routing.
3.3 Unknown identities receive a 403-equivalent rejection with log entry. No data leakage in rejection message.

```python
VALIDATION_FLOW:
  1. Extract sender_id from payload
  2. Query human_network.json: is sender_id in registered_nodes?
  3. If NO  → reject("UNREGISTERED_IDENTITY", log=True)
  4. If YES → extract role: [apex, field_agent, spoke_user]
  5. Attach role to message context → forward to IntentClassifier
```

3.4 Apex Node (Glenn) receives unrestricted routing.
3.5 Field agents receive spoke-scoped routing only — they cannot trigger Vault operations.

---

## SECTION 4: CHANNEL NORMALIZATION

All inbound payloads are normalized to a canonical MessageContext object before classifier ingestion:

```python
@dataclass
class MessageContext:
    sender_id: str
    sender_role: str           # apex | field_agent | spoke_user
    channel: str               # telegram | cli | slack
    raw_text: str
    attachments: list[str]     # URLs or file paths
    timestamp: str             # ISO 8601 UTC
    session_id: str            # for cross-platform continuity
    fidelity_score: float      # set by IntentClassifier, initialized 0.0
```

---

## SECTION 5: RATE LIMITING & CIRCUIT BREAKER

```
Per-user rate limit  : 60 messages/minute
Burst allowance      : 10 messages/5 seconds
Circuit breaker      : if downstream classifier errors > 5 in 60s → open circuit, return fallback message
Flood protection     : if queue depth > 500 → drop non-apex messages, alert Apex via Telegram
```
