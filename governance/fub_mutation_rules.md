# FILE 13: FUB MUTATION RULES
## Follow Up Boss — Zero-Trust API Governance

---

## RULE SET

```python
FUB_MUTATION_RULES = {

    # ─── PASS: Read operations execute immediately ───────────────────────────
    "GET /v1/people":             "PASS",
    "GET /v1/people/{id}":        "PASS",
    "GET /v1/deals":              "PASS",
    "GET /v1/deals/{id}":         "PASS",
    "GET /v1/tasks":              "PASS",
    "GET /v1/tasks/{id}":         "PASS",
    "GET /v1/notes":              "PASS",
    "GET /v1/notes/{id}":         "PASS",
    "GET /v1/pipelines":          "PASS",
    "GET /v1/stages":             "PASS",
    "GET /v1/users":              "PASS",
    "GET /v1/events":             "PASS",

    # ─── FREEZE: Mutations queue for Apex approval ───────────────────────────
    "POST /v1/people":            "FREEZE",   # create lead
    "PUT /v1/people/{id}":        "FREEZE",   # update lead
    "PATCH /v1/people/{id}":      "FREEZE",   # partial update lead
    "POST /v1/deals":             "FREEZE",   # create deal
    "PUT /v1/deals/{id}":         "FREEZE",   # update deal
    "POST /v1/tasks":             "FREEZE",   # create task
    "PUT /v1/tasks/{id}":         "FREEZE",   # update task
    "PATCH /v1/tasks/{id}":       "FREEZE",   # complete/update task
    "POST /v1/notes":             "FREEZE",   # add note
    "PUT /v1/notes/{id}":         "FREEZE",   # update note
    "POST /v1/people/{id}/tags":  "FREEZE",   # tag lead
    "POST /v1/events":            "FREEZE",   # log event

    # ─── HARD KILL: DELETE is unconditional — no Apex escalation ─────────────
    "DELETE /v1/people/{id}":     "HARD_KILL",
    "DELETE /v1/deals/{id}":      "HARD_KILL",
    "DELETE /v1/tasks/{id}":      "HARD_KILL",
    "DELETE /v1/notes/{id}":      "HARD_KILL",
}
```

---

## FREEZE NOTIFICATION TEMPLATE

```
🔒 FUB MUTATION FROZEN
────────────────────────
Operation : {method} {endpoint}
Lead      : {first_name} {last_name} (ID: {lead_id})
Action    : {description}
Spoke     : {spoke_id}
Freeze ID : #{freeze_id}
────────────────────────
Reply: approve {freeze_id} | kill {freeze_id}
```

---

## HARD KILL RESPONSE

```
🚫 FUB DELETE BLOCKED
────────────────────────
Attempted : DELETE {endpoint}
Target    : {resource_id}
Status    : UNCONDITIONALLY BLOCKED
Action    : Request logged. No escalation.
```
