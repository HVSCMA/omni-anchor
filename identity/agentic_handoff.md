# FILE 20: AGENTIC HANDOFF
## CRITICAL: OpenClaw → ClawMem Migration Protocol

---

## ⚠️ PRE-WIPE MANDATORY PROCEDURE

Before Claude Code or any automated process permanently wipes OpenClaw, the following migration MUST be executed and verified. This is a hard prerequisite — no exceptions.

---

## SECTION 1: MIGRATION COMMAND

```bash
hermes claw migrate --source ~/.openclaw \
                    --destination /root/omni-anchor/.clawmem \
                    --verify-integrity \
                    --generate-manifest \
                    --log-path /root/omni-anchor/.clawmem/migration.log
```

---

## SECTION 2: MIGRATION VERIFICATION CHECKLIST

Execute after `hermes claw migrate` completes:

```bash
# Step 1: Verify migration manifest exists
ls -la /root/omni-anchor/.clawmem/migration_manifest.json

# Step 2: Verify integrity hash
hermes claw verify --manifest /root/omni-anchor/.clawmem/migration_manifest.json

# Step 3: Count migrated records
sqlite3 /root/omni-anchor/.clawmem/episodic.db \
  "SELECT COUNT(*) FROM episodes WHERE vault_ref LIKE '%openclaw%';"

# Step 4: Spot-check 5 random migrated memories
hermes memory recall --random 5 --source migrated

# Step 5: Verify skill library migrated
ls /root/omni-anchor/.clawmem/skills/ | wc -l

# Step 6: Write integrity hash to FastSigns archive (File 21)
sha256sum /root/omni-anchor/.clawmem/migration_manifest.json > \
  /root/omni-anchor/vaults/v4-fastsigns/.migration_integrity.sha256
```

---

## SECTION 3: OPENCLAW WIPE — ONLY AFTER VERIFICATION PASSES

```bash
# ONLY execute after ALL 6 verification steps pass
rm -rf ~/.openclaw
echo "OpenClaw wiped. Migration complete. $(date -u)" >> \
  /root/omni-anchor/.clawmem/migration.log
```

---

## SECTION 4: POST-MIGRATION SYSTEM HANDOFF

After migration, Hermes takes over as the sole cognitive engine:

```python
HANDOFF_CHECKLIST = [
    "ClawMem vault paths configured in storage_manifest.yaml",
    "SQLite FTS5 episodic DB initialized",
    "SKILL.md library indexed",
    "MEMORY.md and USER.md injected as frozen prefix-cached snapshots",
    "OpenRouter API key configured (use NEW rotated key — see security note)",
    "Telegram webhook registered with ngrok or direct domain",
    "Docker Compose services started (hermes-core, spokes, redis, nginx)",
    "Validation suite passed (hermes validate --suite full)",
    "Apex Node registered in human_network.json",
    "First Apex communication test complete",
]
```

---

## SECTION 5: BUILDER HANDOFF NOTE

Claude Code's role ends when:
1. All 21 manifest files are written ✓
2. Docker Compose is operational
3. Hermes 0.14.0 is installed and configured
4. Migration from OpenClaw is complete
5. Validation suite passes

After handoff, Willow (Hermes 0.14.0) is the primary cognitive agent. Claude Code returns to its role as infrastructure architect, invoked only for system changes.
