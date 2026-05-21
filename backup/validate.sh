#!/bin/bash
# OMNI-ANCHOR Backup Validation
# Usage: bash validate.sh [backup-dir]
# Exit 0 = PASS, Exit 1 = FAIL
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.env"

BACKUP_DIR="${1:-$(ls -dt "$LOCAL_BACKUP_ROOT"/[0-9]* 2>/dev/null | head -1)}"
[[ -z "$BACKUP_DIR" || ! -d "$BACKUP_DIR" ]] && { echo "No backup directory found"; exit 1; }

PASS=0; FAIL=0; WARN=0

ok()   { echo "  ✓ $*"; PASS=$((PASS+1)); }
fail() { echo "  ✗ $*"; FAIL=$((FAIL+1)); }
warn() { echo "  ⚠ $*"; WARN=$((WARN+1)); }

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "BACKUP VALIDATION: $(basename "$BACKUP_DIR")"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Required files present ─────────────────────────────────────────────────

echo "[1/6] Required files"
REQUIRED=(
  "secrets.tar.gz.enc"
  "clawmem.tar.gz"
  "hermes-state.tar.gz"
  "letsencrypt.tar.gz"
  "systemd-units.tar.gz"
  "dashclaw-postgres.sql.gz"
  "MANIFEST.sha256"
  "MANIFEST.txt"
)
for F in "${REQUIRED[@]}"; do
  [[ -f "$BACKUP_DIR/$F" ]] && ok "$F present" || fail "$F MISSING"
done

# ── 2. Non-zero file sizes ────────────────────────────────────────────────────

echo "[2/6] File sizes non-zero"
for F in "$BACKUP_DIR"/*.{tar.gz,enc,sql.gz} 2>/dev/null; do
  [[ -f "$F" ]] || continue
  SIZE=$(stat -c%s "$F" 2>/dev/null || echo 0)
  FNAME=$(basename "$F")
  if [[ $SIZE -gt 100 ]]; then
    ok "$FNAME: $(du -sh "$F" | cut -f1)"
  else
    fail "$FNAME: suspiciously small (${SIZE} bytes)"
  fi
done

# ── 3. SHA256 manifest verification ──────────────────────────────────────────

echo "[3/6] Checksum integrity"
if [[ -f "$BACKUP_DIR/MANIFEST.sha256" ]]; then
  cd "$BACKUP_DIR"
  while IFS= read -r LINE; do
    HASH=$(echo "$LINE" | awk '{print $1}')
    FILE=$(echo "$LINE" | awk '{print $2}')
    [[ -f "$FILE" ]] || continue
    ACTUAL=$(sha256sum "$FILE" | awk '{print $1}')
    if [[ "$HASH" == "$ACTUAL" ]]; then
      ok "checksum OK: $FILE"
    else
      fail "checksum MISMATCH: $FILE"
    fi
  done < MANIFEST.sha256
else
  fail "MANIFEST.sha256 not found"
fi

# ── 4. Archive integrity (tar test) ──────────────────────────────────────────

echo "[4/6] Archive integrity"
for F in "$BACKUP_DIR"/*.tar.gz; do
  [[ -f "$F" ]] || continue
  FNAME=$(basename "$F")
  if tar -tzf "$F" &>/dev/null; then
    COUNT=$(tar -tzf "$F" 2>/dev/null | wc -l)
    ok "$FNAME: readable ($COUNT entries)"
  else
    fail "$FNAME: corrupt or unreadable"
  fi
done

# ── 5. Encrypted archive decryptable ─────────────────────────────────────────

echo "[5/6] Encrypted secrets decryptable"
if [[ -f "$BACKUP_DIR/secrets.tar.gz.enc" && -f "$BACKUP_KEY_FILE" ]]; then
  KEY=$(cat "$BACKUP_KEY_FILE")
  if openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 -pass "pass:$KEY" \
      -in "$BACKUP_DIR/secrets.tar.gz.enc" 2>/dev/null | tar -tz &>/dev/null; then
    FILES=$(openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 -pass "pass:$KEY" \
      -in "$BACKUP_DIR/secrets.tar.gz.enc" 2>/dev/null | tar -tz 2>/dev/null | tr '\n' ' ')
    ok "secrets decryptable — contents: $FILES"
  else
    fail "secrets.tar.gz.enc: decryption failed"
  fi
else
  warn "Cannot validate secrets — key file or archive missing"
fi

# ── 6. PostgreSQL dump sanity ─────────────────────────────────────────────────

echo "[6/6] PostgreSQL dump sanity"
if [[ -f "$BACKUP_DIR/dashclaw-postgres.sql.gz" ]]; then
  TABLES=$(zcat "$BACKUP_DIR/dashclaw-postgres.sql.gz" 2>/dev/null | grep -c "^CREATE TABLE" || echo 0)
  if [[ $TABLES -gt 5 ]]; then
    ok "postgres dump contains $TABLES CREATE TABLE statements"
  else
    warn "postgres dump: only $TABLES tables detected (expected 90+)"
  fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [[ $FAIL -eq 0 ]]; then
  echo "VALIDATION PASSED — $PASS checks OK, $WARN warnings"
  exit 0
else
  echo "VALIDATION FAILED — $FAIL failures, $WARN warnings, $PASS passed"
  exit 1
fi
