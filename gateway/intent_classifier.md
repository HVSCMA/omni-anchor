# FILE 04: INTENT CLASSIFIER
## Tier 1 Semantic Triage + Prompt Fidelity Calculator

---

## SECTION 1: CLASSIFIER ROLE

The Intent Classifier is the first cognitive layer. It runs exclusively on Tier 1 models (Llama 3 8B/70B via OpenRouter) to minimize cost and maximize throughput. Its sole job is:

1. Classify intent into an action category
2. Calculate Prompt Fidelity Score
3. Route to the correct ClawMem vault or spoke

---

## SECTION 2: INTENT TAXONOMY

```
CATEGORY              VAULT/ROUTE         TIER
─────────────────────────────────────────────────────
crm.fub.read          Vault 1 / FUB GET   1
crm.fub.mutate        Vault 1 / FUB FREEZE→Apex  2
crm.sierra.read       Vault 1 / Sierra GET  1
crm.sierra.mutate     Vault 1 / Sierra FREEZE→Apex  2
crm.fello.read        Vault 1 / Fello GET  1
crm.fello.mutate      Vault 1 / Fello FREEZE→Apex  2
memory.recall         ClawMem SQLite FTS5  1
memory.store          ClawMem write path   1
design.hyperframes    Vault 2 / HyperFrames  2
mthi.cross_pollinate  Vault 3 (read-only)  2
spoke.delegate        A2A Protocol         1
system.apex_override  Direct to Apex queue  bypass
unknown               Rejection + clarification request  1
```

---

## SECTION 3: PROMPT FIDELITY CALCULATOR

```python
def calculate_fidelity(intent_category: str, parsed_fields: dict) -> float:
    """
    Returns fidelity score 0.0 to 1.0.
    1.0 = all required fields present and schema-verified.
    < 1.0 = missing or unverifiable fields → REJECT.
    """
    required = SCHEMA_REQUIREMENTS[intent_category]
    verified = 0
    missing = []

    for field, validator in required.items():
        value = parsed_fields.get(field)
        if value is not None and validator(value):
            verified += 1
        else:
            missing.append(field)

    score = verified / len(required) if required else 1.0

    if score < 1.0:
        raise FidelityError(
            score=score,
            missing_fields=missing,
            message=f"REJECTED: Prompt fidelity {score:.2%}. Missing: {missing}. "
                    f"Provide exact values for all required fields. No inference permitted."
        )
    return score
```

---

## SECTION 4: SCHEMA REQUIREMENTS MAP

```python
SCHEMA_REQUIREMENTS = {
    "crm.fub.mutate": {
        "first_name": lambda v: isinstance(v, str) and v.isalpha(),
        "last_name":  lambda v: isinstance(v, str) and v.isalpha(),
        "action":     lambda v: v in ["create", "update", "add_task", "add_note"],
        "spoke_id":   lambda v: isinstance(v, int),
    },
    "crm.fello.mutate": {
        "street":     lambda v: isinstance(v, str) and len(v) > 0,
        "city":       lambda v: isinstance(v, str) and len(v) > 0,
        "state":      lambda v: isinstance(v, str) and len(v) == 2,
        "zip":        lambda v: isinstance(v, str) and v.isdigit() and len(v) == 5,
        "valuation":  lambda v: isinstance(v, int) and v > 0,
        "sequence_trigger": lambda v: isinstance(v, bool),
    },
    "crm.sierra.mutate": {
        "mls_number": lambda v: isinstance(v, int) and v > 0,
        "action":     lambda v: v in ["save_search", "track_view"],
    },
    # Read operations have no fidelity requirement — they pass through
    "crm.fub.read":     {},
    "crm.sierra.read":  {},
    "crm.fello.read":   {},
    "memory.recall":    {},
    "spoke.delegate":   {"target_spoke": lambda v: v in ["heather","alpha","beta","gamma"]},
}
```

---

## SECTION 5: TIER 1 CLASSIFIER PROMPT TEMPLATE

```
SYSTEM: You are a routing classifier. Respond ONLY with JSON. No prose.
OUTPUT FORMAT: {"category": "<category>", "parsed_fields": {<key:value pairs>}, "confidence": <0.0-1.0>}

CATEGORIES: crm.fub.read | crm.fub.mutate | crm.sierra.read | crm.sierra.mutate |
            crm.fello.read | crm.fello.mutate | memory.recall | memory.store |
            design.hyperframes | mthi.cross_pollinate | spoke.delegate | unknown

USER MESSAGE: {raw_text}
```

Model: `meta-llama/llama-3-8b-instruct` (OpenRouter)
Max tokens: 200
Temperature: 0.0 (deterministic)
