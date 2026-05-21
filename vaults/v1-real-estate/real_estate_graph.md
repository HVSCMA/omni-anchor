# FILE 08: REAL ESTATE GRAPH
## Vault 1 — Hudson Valley & Suncoast Transaction Engine
## Sales Objections → Psychological Triggers Map

---

## SECTION 1: MARKET TOPOLOGY

```yaml
markets:
  hudson_valley:
    regions: ["Dutchess County", "Ulster County", "Orange County", "Putnam County"]
    crm_primary: FUB
    crm_secondary: Sierra
    valuation_platform: Fello
    spoke_owner: spoke-heather

  suncoast:
    regions: ["Sarasota County", "Manatee County", "Charlotte County"]
    crm_primary: FUB
    crm_secondary: Sierra
    valuation_platform: Fello
    spoke_owner: spoke-alpha
```

---

## SECTION 2: PIPELINE STATE REGISTRY

FUB pipeline stages map strictly to integer IDs. No string inference permitted.

```python
FUB_PIPELINE_STAGES = {
    1:  "New Lead",
    2:  "Attempted Contact",
    3:  "Active Prospect",
    4:  "Under Contract",
    5:  "Closed Won",
    6:  "Closed Lost",
    7:  "Long-Term Nurture",
    8:  "Referral Source",
    9:  "Past Client",
    10: "Sphere of Influence"
}
```

---

## SECTION 3: SALES OBJECTIONS → PSYCHOLOGICAL TRIGGERS

```python
OBJECTION_TRIGGER_MAP = {
    "not the right time": {
        "psychological_trigger": "temporal_anchoring",
        "response_protocol": "acknowledge + market_data_injection + future_pace",
        "fub_action": "move_to_long_term_nurture",
        "follow_up_days": 30
    },
    "price too high": {
        "psychological_trigger": "loss_aversion",
        "response_protocol": "comparable_sales_pull + equity_framing",
        "fub_action": "schedule_task_market_update",
        "follow_up_days": 7
    },
    "need to sell first": {
        "psychological_trigger": "sequential_dependency",
        "response_protocol": "bridge_loan_education + simultaneous_close_framing",
        "fub_action": "tag_contingent_seller",
        "follow_up_days": 14
    },
    "just looking": {
        "psychological_trigger": "curiosity_without_commitment",
        "response_protocol": "value_delivery_no_ask + sierra_search_setup",
        "fub_action": "move_to_active_prospect",
        "follow_up_days": 3
    },
    "working with another agent": {
        "psychological_trigger": "loyalty_and_sunk_cost",
        "response_protocol": "relationship_audit + differentiation_proof",
        "fub_action": "tag_competitor_engaged",
        "follow_up_days": 60
    },
    "rates are too high": {
        "psychological_trigger": "payment_anchoring",
        "response_protocol": "rate_buydown_education + historical_rate_context",
        "fub_action": "schedule_task_lender_intro",
        "follow_up_days": 7
    }
}
```

---

## SECTION 4: RECEPTOR MATRICES

See dedicated files:
- `fub_receptor_matrix.md` (File 08A)
- `sierra_receptor_matrix.md` (File 08B)
- `fello_receptor_matrix.md` (File 08C)
