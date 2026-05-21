# FILE 15: FELLO MUTATION RULES
## Fello Seller Platform — Zero-Trust API Governance

---

## RULE SET

```python
FELLO_MUTATION_RULES = {

    # ─── PASS: Valuation queries execute immediately ──────────────────────────
    "GET /api/valuations":                 "PASS",
    "GET /api/valuations/{address_id}":    "PASS",
    "POST /api/valuations/lookup":         "PASS",    # read-equivalent: address → AVM value
    "GET /api/sellers":                    "PASS",
    "GET /api/sellers/{id}":               "PASS",
    "GET /api/sequences":                  "PASS",
    "GET /api/sequences/{id}/status":      "PASS",

    # ─── FREEZE: Seller trigger mutations queue for Apex approval ─────────────
    "POST /api/sellers":                   "FREEZE",  # register new seller
    "PUT /api/sellers/{id}":               "FREEZE",  # update seller record
    "PATCH /api/sellers/{id}":             "FREEZE",  # partial update
    "POST /api/sellers/{id}/sequences":    "FREEZE",  # enroll seller in sequence
    "PUT /api/sellers/{id}/sequences":     "FREEZE",  # update sequence enrollment
    "PATCH /api/sellers/{id}/sequences":   "FREEZE",  # modify sequence state
    "POST /api/valuations/{id}/trigger":   "FREEZE",  # trigger valuation outreach

    # ─── HARD KILL: DELETE unconditionally blocked ────────────────────────────
    "DELETE /api/sellers/{id}":            "HARD_KILL",
    "DELETE /api/sellers/{id}/sequences":  "HARD_KILL",
    "DELETE /api/valuations/{id}":         "HARD_KILL",
}
```

---

## SEQUENCE TRIGGER FREEZE — CRITICAL NOTE

Fello sequence triggers initiate automated seller outreach campaigns. Enrolling or unenrolling a seller in a sequence has direct communication and legal implications. All sequence trigger mutations are frozen pending explicit Apex approval.

---

## VALUATION LOOKUP — PASS-THROUGH SCHEMA CHECK

Even though valuation lookups pass through automatically, they still pass through the Fello Receptor Matrix (File 08C) to ensure the address is properly parsed before the API call is made.

```python
async def fello_valuation_lookup(raw_address: dict) -> ValuationResult:
    # Receptor matrix validation still applies to read operations
    validated = fello_receptor.validate_address(raw_address)
    return await fello_api.get_valuation(validated)
```

---

## FREEZE NOTIFICATION TEMPLATE

```
🔒 FELLO MUTATION FROZEN
────────────────────────
Operation : {method} {endpoint}
Seller    : {address_street}, {address_city} {address_state}
Action    : {description}
Sequence  : {sequence_name if applicable}
Freeze ID : #{freeze_id}
────────────────────────
Reply: approve {freeze_id} | kill {freeze_id}
```
