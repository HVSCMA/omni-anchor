# FILE 08A: FUB RECEPTOR MATRIX
## Follow Up Boss — Deterministic Schema Enforcement
## Anchored to File 08 (Real Estate Graph)

---

## IDENTITY FIELDS

```python
IDENTITY_SCHEMA = {
    "first_name": {
        "type": str,
        "validator": lambda v: v.isalpha() and len(v) > 0,
        "error": "First name must be alphabetic string only. No numbers or symbols."
    },
    "last_name": {
        "type": str,
        "validator": lambda v: v.isalpha() and len(v) > 0,
        "error": "Last name must be alphabetic string only. No numbers or symbols."
    }
}
```

---

## CONTACT ARRAY

```python
PHONE_SCHEMA = {
    "number": {
        "type": str,
        "validator": lambda v: v.isdigit() and len(v) in [10, 11],
        "error": "Phone must be integer string (10 or 11 digits). No dashes, spaces, or symbols."
    },
    "label": {
        "type": str,
        "validator": lambda v: v in ["mobile", "work", "home"],
        "error": "Phone label must be exactly: mobile | work | home"
    }
}

EMAIL_SCHEMA = {
    "address": {
        "type": str,
        "validator": lambda v: re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', v) is not None,
        "error": "Email must pass standard format validation (local@domain.tld)."
    }
}
```

---

## PIPELINE STATE

```python
PIPELINE_SCHEMA = {
    "stage_id": {
        "type": int,
        "validator": lambda v: v in FUB_PIPELINE_STAGES,  # see File 08
        "error": f"Pipeline stage must be integer ID from: {list(FUB_PIPELINE_STAGES.keys())}. "
                 "No inferred language (e.g., 'nurture' is not valid — use 7)."
    }
}
```

---

## TASKS

```python
TASK_SCHEMA = {
    "action_type": {
        "type": str,
        "validator": lambda v: v in ["call", "email", "text", "appointment", "follow_up", "other"],
        "error": "Task action_type must be: call | email | text | appointment | follow_up | other"
    },
    "due_date": {
        "type": str,
        "validator": lambda v: bool(re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$', v)),
        "error": "Due date must be ISO 8601 UTC format: YYYY-MM-DDTHH:MM:SSZ"
    },
    "spoke_id": {
        "type": int,
        "validator": lambda v: isinstance(v, int) and v > 0,
        "error": "spoke_id must be a positive integer."
    }
}
```

---

## NOTES

```python
NOTE_SCHEMA = {
    "subject": {
        "type": str,
        "validator": lambda v: isinstance(v, str) and len(v) > 0,
        "error": "Note subject line is required."
    },
    "target_lead_id": {
        "type": str,
        "validator": lambda v: isinstance(v, str) and len(v) > 0,
        "error": "target_lead_id (FUB lead ID) is required."
    },
    "body": {
        "type": str,
        "validator": lambda v: isinstance(v, str) and len(v) > 0,
        "error": "Note body is required."
    }
}
```

---

## FIDELITY ENFORCEMENT

All FUB mutation requests must pass 100% schema validation before any API call is made. Any field failing validation causes the entire request to be rejected with a structured error listing every failed field and its constraint.
