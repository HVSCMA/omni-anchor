#!/bin/bash
# OMNI-ANCHOR Restore Step 2 — Decrypt and restore secrets (.env files)
# Must run before any services are started
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../config.env"

BACKUP_DIR="${1:-}"
[[ -z "$BACKUP_DIR" ]] && { echo "Usage: $0 <backup-dir>"; exit 1; }
[[ -d "$BACKUP_DIR" ]] || { echo "Backup dir not found: $BACKUP_DIR"; exit 1; }
[[ -f "$BACKUP_DIR/secrets.tar.gz.enc" ]] || { echo "secrets.tar.gz.enc not found in $BACKUP_DIR"; exit 1; }

ok()   { echo "  ✓ $*"; }
warn() { echo "  ⚠ $*"; }
die()  { echo "  ✗ FATAL: $*"; exit 1; }

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "RESTORE STEP 2 — Secrets"
echo "  Backup: $(basename "$BACKUP_DIR")"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Locate encryption key ─────────────────────────────────────────────────────

if [[ -f "$BACKUP_KEY_FILE" ]]; then
  KEY=$(cat "$BACKUP_KEY_FILE")
  ok "Encryption key found at $BACKUP_KEY_FILE"
else
  echo "  ✗ Key file not found at $BACKUP_KEY_FILE"
  echo "    Enter backup key manually (64-char hex):"
  read -rs KEY
  echo ""
  [[ ${#KEY} -ge 16 ]] || die "Key too short — aborting"
  echo "$KEY" > "$BACKUP_KEY_FILE"
  chmod 600 "$BACKUP_KEY_FILE"
  ok "Key saved to $BACKUP_KEY_FILE"
fi

# ── Decrypt to temp directory ─────────────────────────────────────────────────

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 -pass "pass:$KEY" \
  -in "$BACKUP_DIR/secrets.tar.gz.enc" 2>/dev/null \
  | tar -xz -C "$TMPDIR" \
  || die "Decryption failed — check key"

ok "Secrets decrypted to temp dir"
echo "  Contents: $(ls "$TMPDIR" | tr '\n' ' ')"

# ── Restore .env files ────────────────────────────────────────────────────────

# omni-anchor .env
if [[ -f "$TMPDIR/omni-anchor.env" ]]; then
  mkdir -p "$OMNI_ROOT"
  cp "$TMPDIR/omni-anchor.env" "$OMNI_ROOT/.env"
  chmod 600 "$OMNI_ROOT/.env"
  ok "Restored $OMNI_ROOT/.env"
else
  warn "omni-anchor.env not in backup"
fi

# hermes .env
if [[ -f "$TMPDIR/hermes.env" ]]; then
  mkdir -p "/usr/local/lib/hermes-agent"
  cp "$TMPDIR/hermes.env" "/usr/local/lib/hermes-agent/.env"
  chmod 600 "/usr/local/lib/hermes-agent/.env"
  ok "Restored /usr/local/lib/hermes-agent/.env"
else
  warn "hermes.env not in backup"
fi

# dashclaw .env.local
if [[ -f "$TMPDIR/dashclaw.env" ]]; then
  mkdir -p "$DASHCLAW_ROOT"
  cp "$TMPDIR/dashclaw.env" "$DASHCLAW_ROOT/.env.local"
  chmod 600 "$DASHCLAW_ROOT/.env.local"
  ok "Restored $DASHCLAW_ROOT/.env.local"
else
  warn "dashclaw.env not in backup"
fi

# restore backup key from archive if not already present on disk
if [[ -f "$TMPDIR/backup.key.DO-NOT-LOSE" && ! -s "$BACKUP_KEY_FILE" ]]; then
  cp "$TMPDIR/backup.key.DO-NOT-LOSE" "$BACKUP_KEY_FILE"
  chmod 600 "$BACKUP_KEY_FILE"
  ok "Backup key re-saved to $BACKUP_KEY_FILE"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "SECRETS RESTORE COMPLETE"
echo "Next step: bash 03-services.sh $BACKUP_DIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
