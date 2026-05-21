#!/bin/bash
# OMNI-ANCHOR Restore Step 5 — Agent state: ClawMem, Hermes soul/memory, Claude memory
# Stop hermes-gateway.service before running this step
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../config.env"

BACKUP_DIR="${1:-}"
[[ -z "$BACKUP_DIR" ]] && { echo "Usage: $0 <backup-dir>"; exit 1; }
[[ -d "$BACKUP_DIR" ]] || { echo "Backup dir not found: $BACKUP_DIR"; exit 1; }

ok()   { echo "  ✓ $*"; }
warn() { echo "  ⚠ $*"; }
info() { echo "  → $*"; }

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "RESTORE STEP 5 — Agent State"
echo "  Backup: $(basename "$BACKUP_DIR")"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Ensure hermes-gateway is stopped to avoid write conflicts
if systemctl --user is-active hermes-gateway.service &>/dev/null 2>&1; then
  systemctl --user stop hermes-gateway.service
  ok "hermes-gateway.service stopped"
fi

# ── ClawMem (episodic memory DB) ──────────────────────────────────────────────

echo "[ClawMem] Restoring episodic memory…"
if [[ -f "$BACKUP_DIR/clawmem.tar.gz" ]]; then
  # Back up current state before overwriting
  if [[ -d "$OMNI_ROOT/.clawmem" ]]; then
    mv "$OMNI_ROOT/.clawmem" "$OMNI_ROOT/.clawmem.pre-restore.$(date +%H%M%S)"
    info "Existing ClawMem moved to .clawmem.pre-restore.*"
  fi
  mkdir -p "$OMNI_ROOT"
  tar -xzf "$BACKUP_DIR/clawmem.tar.gz" -C "$OMNI_ROOT/"
  # Repair WAL state after restore
  if [[ -f "$OMNI_ROOT/.clawmem/episodic.db" ]]; then
    sqlite3 "$OMNI_ROOT/.clawmem/episodic.db" "PRAGMA integrity_check;" &>/dev/null && \
      ok "ClawMem restored — integrity OK" || warn "ClawMem integrity check failed"
  else
    warn "episodic.db not found after extract — check archive"
  fi
else
  warn "clawmem.tar.gz not in backup"
fi

# ── Hermes State ──────────────────────────────────────────────────────────────

echo "[Hermes] Restoring soul, config, memories, sessions…"
if [[ -f "$BACKUP_DIR/hermes-state.tar.gz" ]]; then
  # Pre-restore snapshot
  if [[ -d "$HERMES_HOME" ]]; then
    PRERESTORE="$HERMES_HOME.pre-restore.$(date +%H%M%S)"
    cp -a "$HERMES_HOME" "$PRERESTORE"
    info "Existing Hermes state backed up → $PRERESTORE"
    # Remove mutable state dirs but keep binaries/plugins if any
    rm -rf "$HERMES_HOME/memories" "$HERMES_HOME/sessions" \
           "$HERMES_HOME/state.db" "$HERMES_HOME/kanban.db" \
           "$HERMES_HOME/SOUL.md" "$HERMES_HOME/config.yaml"
  fi
  mkdir -p "$HERMES_HOME"
  # Extract preserving relative paths from archive root
  tar -xzf "$BACKUP_DIR/hermes-state.tar.gz" -C /
  # Repair SQLite WAL files
  for DB in "$HERMES_HOME/state.db" "$HERMES_HOME/kanban.db"; do
    if [[ -f "$DB" ]]; then
      sqlite3 "$DB" "PRAGMA wal_checkpoint(TRUNCATE);" 2>/dev/null && \
        ok "$(basename "$DB") WAL checkpointed" || warn "$(basename "$DB") checkpoint failed"
    fi
  done

  MEMORY_COUNT=$(find "$HERMES_HOME/memories" -name "*.md" 2>/dev/null | wc -l)
  SESSION_COUNT=$(find "$HERMES_HOME/sessions" -name "*.json" 2>/dev/null | wc -l)
  ok "Hermes state restored — $MEMORY_COUNT memories, $SESSION_COUNT sessions"
  [[ -f "$HERMES_HOME/SOUL.md" ]] && ok "SOUL.md present" || warn "SOUL.md missing"
else
  warn "hermes-state.tar.gz not in backup"
fi

# ── Claude Memory ──────────────────────────────────────────────────────────────

echo "[Claude] Restoring Claude memory files…"
CLAUDE_MEM="/root/.claude/projects/-root/memory"
if [[ -f "$BACKUP_DIR/claude-memory.tar.gz" ]]; then
  if [[ -d "$CLAUDE_MEM" ]]; then
    mv "$CLAUDE_MEM" "${CLAUDE_MEM}.pre-restore.$(date +%H%M%S)"
    info "Existing Claude memory moved to .pre-restore.*"
  fi
  mkdir -p "$(dirname "$CLAUDE_MEM")"
  tar -xzf "$BACKUP_DIR/claude-memory.tar.gz" -C "/root/.claude/projects/-root/"
  MEM_COUNT=$(find "$CLAUDE_MEM" -name "*.md" 2>/dev/null | wc -l)
  ok "Claude memory restored — $MEM_COUNT files"
else
  warn "claude-memory.tar.gz not in backup"
fi

# ── Restart hermes-gateway ────────────────────────────────────────────────────

echo "[Hermes] Starting hermes-gateway.service…"
if [[ -f "$HOME/.config/systemd/user/hermes-gateway.service" ]]; then
  systemctl --user start hermes-gateway.service 2>/dev/null && \
    ok "hermes-gateway.service started" || warn "hermes-gateway start failed — check: journalctl --user -u hermes-gateway"
else
  warn "hermes-gateway.service unit file not found — run step 03 first"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STATE RESTORE COMPLETE"
echo "  hermes: $(systemctl --user is-active hermes-gateway.service 2>/dev/null || echo 'n/a')"
echo "Next step: bash 06-verify.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
