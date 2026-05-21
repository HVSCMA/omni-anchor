# FILE 14: SIERRA MUTATION RULES
## Sierra Interactive — Zero-Trust API Governance

---

## RULE SET

```python
SIERRA_MUTATION_RULES = {

    # ─── PASS: Behavioral tracking executes immediately ──────────────────────
    "GET /api/leads":                      "PASS",
    "GET /api/leads/{id}":                 "PASS",
    "GET /api/leads/{id}/activity":        "PASS",
    "GET /api/searches":                   "PASS",
    "GET /api/properties/viewed":          "PASS",
    "GET /api/properties/{mls}":           "PASS",
    "POST /api/leads/{id}/track_view":     "PASS",    # behavioral event — read-equivalent
    "POST /api/leads/{id}/track_search":   "PASS",    # behavioral event — read-equivalent

    # ─── FREEZE: Lead routing mutations queue for Apex approval ──────────────
    "POST /api/leads":                     "FREEZE",  # create lead in Sierra
    "PUT /api/leads/{id}":                 "FREEZE",  # update lead record
    "PATCH /api/leads/{id}":               "FREEZE",  # partial update
    "POST /api/leads/{id}/assign":         "FREEZE",  # assign to agent
    "PUT /api/leads/{id}/assign":          "FREEZE",  # reassign lead
    "POST /api/searches":                  "FREEZE",  # create saved search
    "PUT /api/searches/{id}":              "FREEZE",  # update saved search
    "POST /api/leads/{id}/campaigns":      "FREEZE",  # enroll in campaign

    # ─── HARD KILL: DELETE unconditionally blocked ───────────────────────────
    "DELETE /api/leads/{id}":             "HARD_KILL",
    "DELETE /api/searches/{id}":          "HARD_KILL",
    "DELETE /api/leads/{id}/campaigns":   "HARD_KILL",
}
```

---

## LEAD ROUTING FREEZE — CRITICAL NOTE

Lead routing in Sierra has downstream financial consequences (agent commissions, accountability). Any routing mutation is frozen regardless of urgency. The Apex Node is the sole authority to approve routing changes.

---

## FREEZE NOTIFICATION TEMPLATE

```
🔒 SIERRA MUTATION FROZEN
────────────────────────
Operation : {method} {endpoint}
Lead      : {lead_id}
Action    : {description}
Freeze ID : #{freeze_id}
────────────────────────
Reply: approve {freeze_id} | kill {freeze_id}
```
