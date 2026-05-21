#!/bin/bash
# OMNI-ANCHOR Restore Step 6 — Post-restore health verification
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../config.env"

PASS=0; FAIL=0; WARN=0

ok()   { echo "  ✓ $*"; PASS=$((PASS+1)); }
fail() { echo "  ✗ $*"; FAIL=$((FAIL+1)); }
warn() { echo "  ⚠ $*"; WARN=$((WARN+1)); }
check_http() {
  local URL="$1" EXPECT="${2:-200}" LABEL="${3:-$1}"
  local STATUS
  STATUS=$(curl -sk -o /dev/null -w "%{http_code}" --max-time 5 "$URL" 2>/dev/null)
  if [[ "$STATUS" == "$EXPECT" ]]; then
    ok "$LABEL → HTTP $STATUS"
  else
    fail "$LABEL → HTTP $STATUS (expected $EXPECT)"
  fi
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "RESTORE VERIFICATION"
echo "  $(date)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Systemd services (system) ──────────────────────────────────────────────

echo "[1] System services"
for SVC in mcp-interceptor fello-webhook; do
  if systemctl is-active --quiet "$SVC"; then
    ok "$SVC: active"
  else
    fail "$SVC: NOT active (systemctl start $SVC)"
  fi
done

# ── 2. User services ──────────────────────────────────────────────────────────

echo "[2] User services"
if systemctl --user is-active --quiet hermes-gateway; then
  ok "hermes-gateway: active"
else
  warn "hermes-gateway: not active (may take a moment or need step 05)"
fi

# ── 3. Docker containers ──────────────────────────────────────────────────────

echo "[3] Docker containers"
for CONTAINER in nginx redis dashclaw-db-1; do
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${CONTAINER}$"; then
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null || echo "running")
    ok "$CONTAINER: running ($STATUS)"
  else
    fail "$CONTAINER: NOT running"
  fi
done

# ── 4. Port connectivity ──────────────────────────────────────────────────────

echo "[4] Port connectivity"
for PORT_LABEL in "8000:MCP Interceptor" "8100:Fello Webhook"; do
  PORT="${PORT_LABEL%%:*}"
  LABEL="${PORT_LABEL#*:}"
  if curl -sk --max-time 3 "http://localhost:$PORT/health" -o /dev/null; then
    ok "$LABEL (:$PORT): reachable"
  else
    fail "$LABEL (:$PORT): not responding on /health"
  fi
done

if docker exec redis redis-cli ping 2>/dev/null | grep -q PONG; then
  ok "Redis (:6379): PONG"
else
  fail "Redis: no PONG"
fi

if docker exec dashclaw-db-1 pg_isready -U dashclaw &>/dev/null 2>&1; then
  ok "PostgreSQL (:5433): ready"
else
  fail "PostgreSQL: not ready"
fi

# ── 5. TLS certificates ───────────────────────────────────────────────────────

echo "[5] TLS certificates"
CERT=/etc/letsencrypt/live/hvsold.com/fullchain.pem
if [[ -f "$CERT" ]]; then
  EXPIRY=$(openssl x509 -noout -enddate -in "$CERT" 2>/dev/null | cut -d= -f2)
  DAYS=$(( ( $(date -d "$EXPIRY" +%s) - $(date +%s) ) / 86400 ))
  if [[ $DAYS -gt 14 ]]; then
    ok "TLS cert valid — expires in $DAYS days ($EXPIRY)"
  else
    warn "TLS cert expires in $DAYS days — renew soon"
  fi
else
  fail "TLS cert not found at $CERT"
fi

# ── 6. HTTP endpoints ─────────────────────────────────────────────────────────

echo "[6] HTTP endpoints"
check_http "https://widget.hvsold.com" "200" "widget.hvsold.com"
check_http "https://api.hvsold.com/health" "200" "api.hvsold.com/health"

# ── 7. Critical files ─────────────────────────────────────────────────────────

echo "[7] Critical files"
for F in \
  "$OMNI_ROOT/.env" \
  "$HERMES_HOME/SOUL.md" \
  "$OMNI_ROOT/.clawmem/episodic.db" \
  "$BACKUP_KEY_FILE" \
  "$OMNI_ROOT/nginx/nginx.conf"
do
  [[ -f "$F" ]] && ok "$F present" || fail "$F MISSING"
done

# ── 8. Agent memory ───────────────────────────────────────────────────────────

echo "[8] Agent memory"
MEMORY_COUNT=$(find "$HERMES_HOME/memories" -name "*.md" 2>/dev/null | wc -l)
if [[ $MEMORY_COUNT -gt 0 ]]; then
  ok "Hermes memories: $MEMORY_COUNT files"
else
  warn "Hermes memories: 0 files"
fi

CLAUDE_MEM_COUNT=$(find "/root/.claude/projects/-root/memory" -name "*.md" 2>/dev/null | wc -l)
if [[ $CLAUDE_MEM_COUNT -gt 0 ]]; then
  ok "Claude memory: $CLAUDE_MEM_COUNT files"
else
  warn "Claude memory: 0 files"
fi

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [[ $FAIL -eq 0 ]]; then
  echo "RESTORE VERIFIED — $PASS checks passed, $WARN warnings"
  exit 0
else
  echo "RESTORE INCOMPLETE — $FAIL failures, $WARN warnings, $PASS passed"
  echo "  Review failures above and re-run affected restore steps"
  exit 1
fi
