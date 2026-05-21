# FILE 19: HUMAN NETWORK
## Identity Registry — Apex Node & Field Agent Topology

---

## SECTION 1: NETWORK TOPOLOGY

```
                    ┌─────────────────┐
                    │   APEX NODE     │
                    │ Glenn Fitz. Jr. │
                    │ Global Override │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
       ┌──────┴──────┐ ┌─────┴─────┐ ┌────┴────┐
       │ spoke-heather│ │spoke-alpha│ │spoke-beta│ ...
       │ Hudson Valley│ │ Suncoast  │ │Stillway  │
       └─────────────┘ └───────────┘ └──────────┘
              │              │
       [field agents]  [field agents]
        (quarantined     (quarantined
         visibility)      visibility)
```

---

## SECTION 2: NODE REGISTRY

```python
HUMAN_NETWORK = {
    "apex": {
        "node_id": "apex-001",
        "name": "Glenn Fitzgerald Jr.",
        "role": "apex",
        "telegram_id": "${APEX_TELEGRAM_ID}",    # loaded from env
        "permissions": ["ALL"],
        "override_scope": "GLOBAL",
        "can_approve_freezes": True,
        "can_kill_freezes": True,
        "can_access_all_vaults": True,
        "can_modify_human_network": True
    }
}

# Field agents are registered by spoke, with quarantined visibility
FIELD_AGENT_TEMPLATE = {
    "role": "field_agent",
    "permissions": [
        "crm.fub.read",
        "crm.sierra.read",
        "crm.fello.read",
        "spoke.own.read_write"
    ],
    "can_approve_freezes": False,
    "can_access_vaults": ["v1-real-estate.read_only"],
    "visibility_scope": "own_spoke_only"    # QUARANTINE: field agents see only their spoke
}
```

---

## SECTION 3: FIELD AGENT QUARANTINE

Field agents have **quarantined visibility**:
- They can query leads, properties, and valuations within their spoke scope
- They cannot see other spokes' data
- They cannot initiate mutations (all mutations freeze at Apex)
- They cannot see the MTHI Sanctuary, Stillway vault, or FastSigns archive
- They receive notifications only about their own spoke's activities

```python
def enforce_field_agent_scope(agent_id: str, query: dict) -> dict:
    agent = get_agent(agent_id)
    if agent["role"] == "field_agent":
        # Inject scope filter — agent cannot override this
        query["filters"]["spoke_id"] = agent["spoke_id"]
        query["filters"]["market"] = agent["market"]
    return query
```

---

## SECTION 4: APEX COMMAND INTERFACE

Apex communicates via Telegram. Recognized commands:

```
approve {freeze_id}              → Execute frozen mutation
kill {freeze_id}                 → Cancel frozen mutation
CONFIRM CATASTROPHIC approve {id} → Execute catastrophic mutation
status                           → Show system health + pending freezes
pending                          → List all pending freeze queue items
validate                         → Run validation suite
spoke status                     → Show spoke hibernation states
wake {spoke_id}                  → Resume hibernated spoke
hibernate {spoke_id}             → Force-hibernate a spoke
```

---

## SECTION 5: REGISTERING NEW FIELD AGENTS

Only Apex can register new field agents. Registration command:

```
register agent --name "{name}" --spoke {spoke_id} --telegram {telegram_id}
```

New agent receives a confirmation ping on Telegram with their scope and permissions.
