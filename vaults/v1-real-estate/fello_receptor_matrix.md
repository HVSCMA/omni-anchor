# FILE 08C: FELLO RECEPTOR MATRIX
## Fello Seller Platform — Deterministic Schema Enforcement
## Anchored to File 08 (Real Estate Graph)

---

## ADDRESS PARSING

All address inputs are parsed into discrete logical nodes. No concatenated address strings accepted for mutation operations.

```python
ADDRESS_SCHEMA = {
    "street": {
        "type": str,
        "validator": lambda v: isinstance(v, str) and len(v) > 0,
        "error": "Street address is required as a string."
    },
    "city": {
        "type": str,
        "validator": lambda v: isinstance(v, str) and len(v) > 0,
        "error": "City is required as a string."
    },
    "state": {
        "type": str,
        "validator": lambda v: isinstance(v, str) and len(v) == 2 and v.isupper(),
        "error": "State must be 2-character uppercase abbreviation (e.g., NY, FL)."
    },
    "zip": {
        "type": str,
        "validator": lambda v: isinstance(v, str) and v.isdigit() and len(v) == 5,
        "error": "Zip must be a 5-digit numeric string (e.g., '12601')."
    }
}
```

---

## VALUATION

```python
VALUATION_SCHEMA = {
    "value": {
        "type": int,
        "validator": lambda v: isinstance(v, int) and v > 0,
        "error": "Valuation must be an unformatted positive integer. "
                 "NO currency symbols, commas, or decimal points. "
                 "Correct: 485000  |  REJECTED: $485,000 | '485,000' | 485000.00"
    }
}
```

**Hard enforcement:** Any valuation value containing `$`, `,`, `.`, or passed as a float is rejected at the receptor level before reaching the API client. The rejection message includes the cleaned integer value as a hint.

---

## SEQUENCE TRIGGER

```python
SEQUENCE_TRIGGER_SCHEMA = {
    "active": {
        "type": bool,
        "validator": lambda v: isinstance(v, bool),
        "error": "sequence_trigger must be strict Boolean: True or False. "
                 "REJECTED: 'yes', 'no', 1, 0, 'true', 'false', None."
    }
}
```

**Enforcement note:** Python's `isinstance(v, bool)` check is strict. The integer `1` passes `== True` but fails `isinstance(1, bool)` — this is intentional. Only literal `True` or `False` values are accepted.

---

## SELLER TRIGGER FREEZE

Fello seller sequence triggers (enrolling/unenrolling sellers in automated sequences) are FROZEN pending Apex approval. Valuation queries (GET) pass through automatically.

---

## COMBINED MUTATION PAYLOAD EXAMPLE

```python
# Valid Fello mutation — all fields present and schema-verified
valid_payload = {
    "address": {
        "street": "14 Riverview Terrace",
        "city": "Poughkeepsie",
        "state": "NY",
        "zip": "12601"
    },
    "valuation": {
        "value": 485000          # integer, no formatting
    },
    "sequence_trigger": {
        "active": True           # strict boolean
    }
}
```
