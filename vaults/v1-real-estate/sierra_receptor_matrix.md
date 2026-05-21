# FILE 08B: SIERRA RECEPTOR MATRIX
## Sierra Interactive — Deterministic Schema Enforcement
## Anchored to File 08 (Real Estate Graph)

---

## PROPERTY VIEWS

```python
PROPERTY_VIEW_SCHEMA = {
    "mls_number": {
        "type": int,
        "validator": lambda v: isinstance(v, int) and v > 0,
        "error": "MLS Number must be a positive integer. No strings, no formatting."
    }
}
```

**Enforcement note:** Property view tracking maps strictly to MLS Number as integer. Any request using address strings, partial MLS numbers, or formatted values (e.g., "MLS #12345") is rejected. The caller must resolve the MLS Number before submitting.

---

## SAVED SEARCHES

```python
SAVED_SEARCH_SCHEMA = {
    "price_range": {
        "type": list,
        "validator": lambda v: (
            isinstance(v, list)
            and len(v) == 2
            and all(isinstance(p, int) and p >= 0 for p in v)
            and v[0] <= v[1]
        ),
        "error": "price_range must be [min_int, max_int] — integers only, no symbols, min <= max."
    },
    "polygon": {
        "type": list,
        "validator": lambda v: (
            isinstance(v, list)
            and len(v) >= 3
            and all(
                isinstance(p, dict)
                and isinstance(p.get("lat"), float)
                and isinstance(p.get("lng"), float)
                and -90 <= p["lat"] <= 90
                and -180 <= p["lng"] <= 180
                for p in v
            )
        ),
        "error": "polygon must be array of {lat: float, lng: float} objects. "
                 "Minimum 3 points. Lat: -90 to 90. Lng: -180 to 180."
    },
    "property_type": {
        "type": str,
        "validator": lambda v: v in [
            "single_family", "condo", "townhouse", "multi_family",
            "land", "commercial", "mobile_home"
        ],
        "error": "property_type must be: single_family | condo | townhouse | "
                 "multi_family | land | commercial | mobile_home"
    }
}
```

---

## BEHAVIORAL TRACKING

```python
BEHAVIORAL_TRACKING_SCHEMA = {
    "lead_id": {
        "type": str,
        "validator": lambda v: isinstance(v, str) and len(v) > 0,
        "error": "Sierra lead_id is required."
    },
    "event_type": {
        "type": str,
        "validator": lambda v: v in ["property_view", "search_save", "inquiry", "login"],
        "error": "event_type must be: property_view | search_save | inquiry | login"
    },
    "timestamp": {
        "type": str,
        "validator": lambda v: bool(re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$', v)),
        "error": "timestamp must be ISO 8601 UTC format."
    }
}
```

---

## LEAD ROUTING FREEZE

All Sierra lead routing mutations (assigning/reassigning leads to agents) are FROZEN pending Apex approval. Only behavioral tracking (GET-equivalent events) passes through automatically.
