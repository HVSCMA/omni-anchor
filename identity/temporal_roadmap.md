# FILE 18: TEMPORAL ROADMAP
## Autonomous Hold Protocol — CRM Mutation Freeze Timeline

---

## SECTION 1: HOLD PROTOCOL DEFINITION

The Autonomous Hold Protocol is the system's default stance on CRM mutations. The system does not execute mutations speculatively. It freezes, notifies, and waits. This is not a limitation — it is an intentional design constraint to prevent irreversible data corruption in production CRMs.

---

## SECTION 2: FREEZE STATE MACHINE

```
State: PENDING_APEX_APPROVAL
  Entry: Mutation intercepted by MCP Interceptor
  Actions:
    - Assign freeze_id
    - Serialize payload to freeze queue
    - Notify Apex via Telegram
    - Start hold timer (default: 24 hours)

State: APPROVED
  Transition: Apex sends "approve {freeze_id}"
  Actions:
    - Validate freeze_id exists
    - Execute mutation against CRM API
    - Log outcome to audit trail
    - Notify requester (spoke or direct Apex)

State: KILLED
  Transition: Apex sends "kill {freeze_id}"
  Actions:
    - Remove from freeze queue
    - Log cancellation
    - Notify requester

State: EXPIRED
  Transition: hold timer elapsed without Apex response
  Actions:
    - Move to expired queue (NOT deleted)
    - Notify Apex: "Freeze #{id} expired — still awaiting decision"
    - Keep payload for 7 days before purge
```

---

## SECTION 3: NON-CATASTROPHIC FREEZE DEFAULTS

```python
FREEZE_HOLD_POLICY = {
    "default_hold_hours": 24,
    "escalation_reminder_hours": [6, 12, 20],
    "expired_purge_days": 7,
    "catastrophic_override": False,  # catastrophic events handled differently
    "batch_approval": True,          # Apex can "approve all pending" for batch ops
}
```

---

## SECTION 4: CATASTROPHIC EVENT OVERRIDE

Non-catastrophic mutations (normal CRM updates) follow the 24-hour hold. Catastrophic events (data migration, bulk delete attempt, system account changes) have additional safeguards:

```python
CATASTROPHIC_INDICATORS = [
    "bulk_delete",
    "account_transfer",
    "pipeline_reset",
    "mass_tag_removal",
    "database_migration"
]

def is_catastrophic(operation: str, payload: dict) -> bool:
    payload_str = json.dumps(payload).lower()
    return any(indicator in payload_str for indicator in CATASTROPHIC_INDICATORS)

# Catastrophic mutations: additional confirmation required
# Apex must respond with "CONFIRM CATASTROPHIC approve {freeze_id}" — not just "approve"
```

---

## SECTION 5: TEMPORAL ROUTING SCHEDULE

```yaml
scheduled_operations:
  market_digest:
    schedule: "0 7 * * 1-5"    # weekdays 7am
    description: "Pull FUB pipeline summary + Sierra activity + Fello valuations"
    tier: 1
    freeze_required: false

  weekly_skill_audit:
    schedule: "0 9 * * 0"      # Sunday 9am
    description: "Review SKILL.md entries from past week, prune low-confidence entries"
    tier: 2
    freeze_required: false

  apex_freeze_reminder:
    schedule: "*/6 * * * *"    # every 6 hours
    description: "Check for pending freeze queue items > 6 hours old, re-notify Apex"
    tier: 1
    freeze_required: false
```
