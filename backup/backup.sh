#!/bin/bash
# OMNI-ANCHOR Full-Stack Backup
# Tiers: code → secrets → state → infra → databases
# Usage: bash backup.sh [--dry-run] [--no-offsite]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.env"

DRY_RUN=0; NO_OFFSITE=0
for arg in "$@"; do [[ $arg == --dry-run ]] && DRY_RUN=1; [[ $arg == --no-offsite ]] && NO_OFFSITE=1; done

TIMESTAMP=$(date +%Y-%m-%d_%H-%M)
BACKUP_DIR="$LOCAL_BACKUP_ROOT/$TIMESTAMP"
LOG="$LOCAL_BACKUP_ROOT/last.log"
MANIFEST="$BACKUP_DIR/MANIFEST.sha256"
ERRORS=0

# ── Helpers ───────────────────────────────────────────────────────────────────

log()  { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }
ok()   { log "  ✓ $*"; }
warn() { log "  ⚠ $*"; ERRORS=$((ERRORS+1)); }
die()  { log "  ✗ FATAL: $*"; tg_send "❌ <b>BACKUP FAILED</b>\n$*"; exit 1; }

tg_send() {
  [[ -z "$TG_TOKEN" ]] && return 0
  curl -s -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
    -d chat_id="$TG_CHAT" -d parse_mode="HTML" \
    -d text="$1" -o /dev/null || true
}

encrypt() {
  # encrypt stdin → $1 using AES-256-CBC with key from file
  local KEY; KEY=$(cat "$BACKUP_KEY_FILE")
  openssl enc -aes-256-cbc -pbkdf2 -iter 100000 -pass "pass:$KEY" -out "$1"
}

checksum() {
  # append sha256 of $1 to MANIFEST
  sha256sum "$1" | sed "s|$BACKUP_DIR/||" >> "$MANIFEST"
}

archive() {
  # tar.gz src → dest, then checksum
  local SRC="$1" DEST="$2"
  tar -czf "$DEST" -C "$(dirname "$SRC")" "$(basename "$SRC")" 2>/dev/null || \
  tar -czf "$DEST" $SRC 2>/dev/null
  checksum "$DEST"
}

[[ $DRY_RUN -eq 1 ]] && { log "DRY RUN — no files written"; }

# ── Pre-flight ────────────────────────────────────────────────────────────────

log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "OMNI-ANCHOR BACKUP  $TIMESTAMP"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

[[ -f "$BACKUP_KEY_FILE" ]] || die "Backup key not found at $BACKUP_KEY_FILE"
[[ $DRY_RUN -eq 0 ]] && mkdir -p "$BACKUP_DIR"
> "$LOG"

FREE_KB=$(df -k "$LOCAL_BACKUP_ROOT" | awk 'NR==2{print $4}')
[[ $FREE_KB -lt 524288 ]] && warn "Low disk space: ${FREE_KB}KB free"  # warn under 512MB

# ── Tier 0: Code (git) ───────────────────────────────────────────────────────

log "TIER 0 — Code (git)"

for REPO in "$OMNI_ROOT" "$WIDGET_ROOT"; do
  RNAME=$(basename "$REPO")
  if git -C "$REPO" rev-parse --git-dir &>/dev/null; then
    # Auto-commit any uncommitted changes
    if [[ -n "$(git -C "$REPO" status --porcelain)" ]]; then
      if [[ $DRY_RUN -eq 0 ]]; then
        git -C "$REPO" add -A
        git -C "$REPO" commit -m "chore: auto-backup snapshot $TIMESTAMP" \
          --author="Willow <willow@omni-anchor>" 2>/dev/null || true
      fi
      ok "$RNAME: staged and committed uncommitted changes"
    else
      ok "$RNAME: clean, nothing to commit"
    fi
    # Push if remote configured
    if git -C "$REPO" remote | grep -q .; then
      [[ $DRY_RUN -eq 0 ]] && git -C "$REPO" push --all 2>/dev/null && ok "$RNAME: pushed to remote" || warn "$RNAME: push failed (remote may be unreachable)"
    else
      ok "$RNAME: no remote configured — local only"
    fi
  else
    warn "$RNAME: not a git repo, skipping"
  fi
done

# ── Tier 1: Secrets (encrypted) ──────────────────────────────────────────────

log "TIER 1 — Secrets (AES-256 encrypted)"

if [[ $DRY_RUN -eq 0 ]]; then
  # Bundle all .env files into encrypted archive
  SECRETS_BUNDLE=$(mktemp -d)
  cp "$OMNI_ROOT/.env"                          "$SECRETS_BUNDLE/omni-anchor.env"  2>/dev/null || warn "omni-anchor.env missing"
  cp "/usr/local/lib/hermes-agent/.env"         "$SECRETS_BUNDLE/hermes.env"        2>/dev/null || warn "hermes.env missing"
  cp "$DASHCLAW_ROOT/.env.local"                "$SECRETS_BUNDLE/dashclaw.env"      2>/dev/null || warn "dashclaw.env missing"
  cp "$BACKUP_KEY_FILE"                         "$SECRETS_BUNDLE/backup.key.DO-NOT-LOSE" 2>/dev/null

  tar -czf - -C "$SECRETS_BUNDLE" . | encrypt "$BACKUP_DIR/secrets.tar.gz.enc"
  checksum "$BACKUP_DIR/secrets.tar.gz.enc"
  rm -rf "$SECRETS_BUNDLE"
  ok "secrets.tar.gz.enc written ($(du -sh "$BACKUP_DIR/secrets.tar.gz.enc" | cut -f1))"
fi

# ── Tier 2: State (Hermes + ClawMem) ─────────────────────────────────────────

log "TIER 2 — Agent state (Hermes + ClawMem)"

if [[ $DRY_RUN -eq 0 ]]; then
  # Checkpoint SQLite WAL before backup to ensure consistency
  sqlite3 "$OMNI_ROOT/.clawmem/episodic.db" "PRAGMA wal_checkpoint(TRUNCATE);" 2>/dev/null && ok "ClawMem WAL checkpointed"
  sqlite3 "$HERMES_HOME/state.db"           "PRAGMA wal_checkpoint(TRUNCATE);" 2>/dev/null && ok "Hermes state.db WAL checkpointed"
  sqlite3 "$HERMES_HOME/kanban.db"          "PRAGMA wal_checkpoint(TRUNCATE);" 2>/dev/null || true

  # ClawMem — episodic memory + engine code
  archive "$OMNI_ROOT/.clawmem" "$BACKUP_DIR/clawmem.tar.gz"
  ok "clawmem.tar.gz ($(du -sh "$BACKUP_DIR/clawmem.tar.gz" | cut -f1))"

  # Hermes — soul, config, memories, sessions, state DBs
  # Exclude large cache dirs, audio/image caches, and locks
  tar -czf "$BACKUP_DIR/hermes-state.tar.gz" \
    --exclude="$HERMES_HOME/audio_cache" \
    --exclude="$HERMES_HOME/image_cache" \
    --exclude="$HERMES_HOME/cache" \
    --exclude="$HERMES_HOME/sandboxes" \
    --exclude="$HERMES_HOME/bin" \
    --exclude="$HERMES_HOME/plugins" \
    --exclude="$HERMES_HOME/*.lock" \
    --exclude="$HERMES_HOME/gateway.pid" \
    --exclude="$HERMES_HOME/gateway.lock" \
    "$HERMES_HOME" 2>/dev/null
  checksum "$BACKUP_DIR/hermes-state.tar.gz"
  ok "hermes-state.tar.gz ($(du -sh "$BACKUP_DIR/hermes-state.tar.gz" | cut -f1))"

  # Claude memory
  if [[ -d "/root/.claude/projects/-root/memory" ]]; then
    archive "/root/.claude/projects/-root/memory" "$BACKUP_DIR/claude-memory.tar.gz"
    ok "claude-memory.tar.gz ($(du -sh "$BACKUP_DIR/claude-memory.tar.gz" | cut -f1))"
  fi
fi

# ── Tier 3: Infrastructure ────────────────────────────────────────────────────

log "TIER 3 — Infrastructure (TLS, systemd, nginx)"

if [[ $DRY_RUN -eq 0 ]]; then
  # TLS certs — critical for HTTPS without re-issuing
  archive "$LETSENCRYPT_DIR" "$BACKUP_DIR/letsencrypt.tar.gz"
  ok "letsencrypt.tar.gz ($(du -sh "$BACKUP_DIR/letsencrypt.tar.gz" | cut -f1))"

  # Systemd unit files
  UNITS_DIR=$(mktemp -d)
  for UNIT in mcp-interceptor.service fello-webhook.service; do
    cp "$SYSTEMD_SYSTEM/$UNIT" "$UNITS_DIR/" 2>/dev/null || warn "$UNIT not found"
  done
  cp "$SYSTEMD_USER/hermes-gateway.service" "$UNITS_DIR/hermes-gateway.service" 2>/dev/null || warn "hermes-gateway.service not found"
  tar -czf "$BACKUP_DIR/systemd-units.tar.gz" -C "$UNITS_DIR" . 2>/dev/null
  checksum "$BACKUP_DIR/systemd-units.tar.gz"
  rm -rf "$UNITS_DIR"
  ok "systemd-units.tar.gz"

  # Widget frontend (in case git remote isn't set)
  archive "$WIDGET_ROOT" "$BACKUP_DIR/widget.tar.gz"
  ok "widget.tar.gz ($(du -sh "$BACKUP_DIR/widget.tar.gz" | cut -f1))"
fi

# ── Tier 4: Databases ─────────────────────────────────────────────────────────

log "TIER 4 — Databases (PostgreSQL, Docker volumes)"

if [[ $DRY_RUN -eq 0 ]]; then
  # DashClaw PostgreSQL
  if docker ps --format '{{.Names}}' | grep -q dashclaw-db-1; then
    docker exec dashclaw-db-1 pg_dump -U dashclaw dashclaw \
      | gzip > "$BACKUP_DIR/dashclaw-postgres.sql.gz" 2>/dev/null
    checksum "$BACKUP_DIR/dashclaw-postgres.sql.gz"
    ok "dashclaw-postgres.sql.gz ($(du -sh "$BACKUP_DIR/dashclaw-postgres.sql.gz" | cut -f1))"
  else
    warn "dashclaw-db-1 not running — skipping postgres dump"
  fi

  # Redis RDB snapshot
  REDIS_DATA=$(docker volume inspect omni-anchor_redis-data --format '{{.Mountpoint}}' 2>/dev/null)
  if [[ -n "$REDIS_DATA" && -d "$REDIS_DATA" ]]; then
    # Trigger BGSAVE before backup
    docker exec redis redis-cli BGSAVE 2>/dev/null && sleep 2
    tar -czf "$BACKUP_DIR/redis-data.tar.gz" -C "$REDIS_DATA" . 2>/dev/null
    checksum "$BACKUP_DIR/redis-data.tar.gz"
    ok "redis-data.tar.gz ($(du -sh "$BACKUP_DIR/redis-data.tar.gz" | cut -f1))"
  fi
fi

# ── Manifest + metadata ───────────────────────────────────────────────────────

if [[ $DRY_RUN -eq 0 ]]; then
  log "Writing manifest…"
  {
    echo "# OMNI-ANCHOR Backup Manifest"
    echo "# Timestamp: $TIMESTAMP"
    echo "# Host: $(hostname) ($(curl -s ifconfig.me 2>/dev/null || echo 'unknown'))"
    echo "# Kernel: $(uname -r)"
    echo "# Disk: $(df -h / | awk 'NR==2{print $3"/"$2" used ("$5")"}')"
    echo "# Services: $(systemctl is-active mcp-interceptor fello-webhook 2>/dev/null | tr '\n' ' ')"
    echo "# Git omni-anchor: $(git -C "$OMNI_ROOT" log --oneline -1 2>/dev/null)"
    echo "# Git widget: $(git -C "$WIDGET_ROOT" log --oneline -1 2>/dev/null)"
    echo "#"
    echo "# SHA256 CHECKSUMS"
  } > "$BACKUP_DIR/MANIFEST.txt"
  cat "$MANIFEST" >> "$BACKUP_DIR/MANIFEST.txt"
  checksum "$BACKUP_DIR/MANIFEST.txt"

  BACKUP_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
  ok "Manifest written — backup size: $BACKUP_SIZE"
fi

# ── Validate ──────────────────────────────────────────────────────────────────

if [[ $DRY_RUN -eq 0 ]]; then
  log "Validating backup integrity…"
  bash "$SCRIPT_DIR/validate.sh" "$BACKUP_DIR" 2>&1 | tee -a "$LOG"
fi

# ── Offsite sync ──────────────────────────────────────────────────────────────

if [[ $DRY_RUN -eq 0 && $NO_OFFSITE -eq 0 && -n "$RCLONE_REMOTE" ]]; then
  log "Syncing to offsite: $RCLONE_REMOTE"
  rclone sync "$LOCAL_BACKUP_ROOT" "$RCLONE_REMOTE" $RCLONE_FLAGS \
    --log-level INFO --log-file "$LOG" 2>&1 && ok "Offsite sync complete" || warn "Offsite sync failed"
elif [[ -z "$RCLONE_REMOTE" ]]; then
  log "  ↳ No RCLONE_REMOTE configured — local-only backup"
fi

# ── Rotation ──────────────────────────────────────────────────────────────────

if [[ $DRY_RUN -eq 0 ]]; then
  log "Rotating old backups (keep ${KEEP_DAILY} daily, ${KEEP_WEEKLY} weekly)…"
  cd "$LOCAL_BACKUP_ROOT"

  # Keep all Sunday backups as weeklies (up to KEEP_WEEKLY)
  # Delete dailies beyond KEEP_DAILY
  DIRS=$(ls -d [0-9][0-9][0-9][0-9]-* 2>/dev/null | sort -r)
  DAILY_COUNT=0
  WEEKLY_KEPT=0

  while IFS= read -r DIR; do
    DIR_DATE=$(echo "$DIR" | cut -c1-10)
    DOW=$(date -d "$DIR_DATE" +%u 2>/dev/null || echo 0)  # 7=Sunday

    if [[ $DAILY_COUNT -lt $KEEP_DAILY ]]; then
      DAILY_COUNT=$((DAILY_COUNT+1))
    elif [[ $DOW -eq 7 && $WEEKLY_KEPT -lt $KEEP_WEEKLY ]]; then
      WEEKLY_KEPT=$((WEEKLY_KEPT+1))
    else
      rm -rf "$DIR"
      log "  pruned $DIR"
    fi
  done <<< "$DIRS"
fi

# ── Final report ──────────────────────────────────────────────────────────────

ELAPSED=$(( $(date +%s) - $(date -d "${TIMESTAMP//_/ }" +%s 2>/dev/null || echo $(date +%s)) ))

if [[ $ERRORS -eq 0 ]]; then
  STATUS="✅ <b>BACKUP COMPLETE</b>"
else
  STATUS="⚠️ <b>BACKUP COMPLETE (${ERRORS} warnings)</b>"
fi

MSG="${STATUS}
Timestamp: $TIMESTAMP
Size: ${BACKUP_SIZE:-n/a}
Tiers: code · secrets · state · infra · db
Offsite: ${RCLONE_REMOTE:-local only}
Errors: $ERRORS"

log ""
log "$STATUS — $ERRORS errors"
[[ $DRY_RUN -eq 0 ]] && tg_send "$MSG" || log "(dry run — no TG notification sent)"
