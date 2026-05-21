# FILE 21: FASTSIGNS ARCHIVE
## Vault 4 — Legacy Architectural Takeoff Extraction
## STATUS: EXITED. READ-ONLY ARCHIVE. NO ACTIVE OPERATIONS.

---

## ARCHIVE NOTICE

The FastSigns operational context has been formally exited. This vault exists solely to preserve architectural takeoff data, project logic, and procedural memory from the FastSigns engagement for reference purposes only.

No new data may be written to this vault. No agent may trigger operations based on this vault's contents. The archive is available for read-only historical reference by the Apex Node only.

---

## ARCHIVE CONTENTS SCHEMA

```yaml
archive_version: "1.0"
exited_date: "2025-01-01"     # approximate — update with actual date
status: "read_only_archive"

preserved_assets:
  - type: "architectural_takeoffs"
    description: "Floor plan analysis, material quantity extraction, signage specs"
    format: "structured JSON + PDF references"

  - type: "workflow_procedures"
    description: "Takeoff calculation procedures, client deliverable formats"
    format: "SKILL.md entries"

  - type: "client_data"
    description: "Project records — anonymized per data retention policy"
    format: "SQLite FTS5 index"
    encryption_tier: 1
```

---

## ACCESS POLICY

```python
FASTSIGNS_ACCESS_POLICY = {
    "allowed_operations": ["GET", "SELECT"],
    "blocked_operations": ["POST", "PUT", "PATCH", "DELETE"],
    "allowed_callers": ["hermes-core-apex-session"],
    "requires_apex_auth": True,
    "log_all_reads": True
}
```

---

## MIGRATION NOTE

Per File 20 (Agentic Handoff), all FastSigns historical memory states were migrated from OpenClaw via `hermes claw migrate --source ~/.openclaw` before OpenClaw was decommissioned. Migration integrity hash is stored at `/root/omni-anchor/vaults/v4-fastsigns/.migration_integrity.sha256`.
