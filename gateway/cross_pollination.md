# FILE 05: CROSS-POLLINATION PROTOCOL
## MTHI Sanctuary — Sterile Read-Only Fetch

---

## SECTION 1: PROTOCOL PURPOSE

Cross-pollination allows operational agents to benefit from MTHI spatial logic without contaminating the MTHI Sanctuary (Vault 3). The protocol enforces strict read-only access with automatic post-execution purge.

---

## SECTION 2: FETCH FLOW

```
TRIGGER: Tier 2 task requiring spatial/topological reasoning
           |
           v
  1. Hub requests sterile snapshot from Vault 3 API
  2. Vault 3 API validates: caller = hub, operation = GET only
  3. Snapshot delivered as read-only Python dataclass (frozen=True)
  4. Snapshot injected into Tier 2 model context as system message prefix
  5. Tier 2 model executes task using snapshot data
  6. Task completes → PURGE_HANDLER fires immediately
  7. Snapshot object is deleted from memory + audit log written
```

---

## SECTION 3: STERILE SNAPSHOT STRUCTURE

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class MTHISnapshot:
    """Read-only. Immutable. Auto-purges post-execution."""
    snapshot_id: str
    fetched_at: str           # ISO 8601 UTC
    spatial_nodes: tuple      # tuple enforces immutability
    logic_edges: tuple
    topology_version: str
    expires_at: str           # set to fetched_at + 300s

    def is_expired(self) -> bool:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat() > self.expires_at
```

---

## SECTION 4: PURGE HANDLER

```python
async def purge_mthi_snapshot(snapshot: MTHISnapshot, session_id: str):
    """Called immediately after Tier 2 task completion or on error."""
    del snapshot
    await audit_log.write({
        "event": "mthi_snapshot_purged",
        "session_id": session_id,
        "timestamp": utcnow()
    })
```

---

## SECTION 5: INBOUND WRITE BLOCK

Any agent attempting to write to Vault 3 triggers the following:

```python
def vault3_write_interceptor(caller_id: str, operation: str):
    if operation in ["POST", "PUT", "PATCH", "DELETE"]:
        terminate_agent(caller_id)
        audit_log.write({
            "event": "VAULT3_WRITE_ATTEMPT_BLOCKED",
            "caller": caller_id,
            "severity": "CRITICAL",
            "timestamp": utcnow()
        })
        notify_apex(f"ALERT: Agent {caller_id} attempted MTHI write. Terminated.")
        raise VaultViolationError("MTHI Sanctuary is read-only. Agent terminated.")
```
