#!/bin/bash
# OMNI-ANCHOR Restore Step 3 — Restore and enable systemd unit files
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../config.env"

BACKUP_DIR="${1:-}"
[[ -z "$BACKUP_DIR" ]] && { echo "Usage: $0 <backup-dir>"; exit 1; }
[[ -d "$BACKUP_DIR" ]] || { echo "Backup dir not found: $BACKUP_DIR"; exit 1; }
[[ -f "$BACKUP_DIR/systemd-units.tar.gz" ]] || { echo "systemd-units.tar.gz not in $BACKUP_DIR"; exit 1; }

ok()   { echo "  ✓ $*"; }
warn() { echo "  ⚠ $*"; }
die()  { echo "  ✗ FATAL: $*"; exit 1; }

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "RESTORE STEP 3 — Systemd Services"
echo "  Backup: $(basename "$BACKUP_DIR")"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

tar -xzf "$BACKUP_DIR/systemd-units.tar.gz" -C "$TMPDIR"
ok "Extracted: $(ls "$TMPDIR" | tr '\n' ' ')"

# ── System units (root) ────────────────────────────────────────────────────────

for UNIT in mcp-interceptor.service fello-webhook.service; do
  if [[ -f "$TMPDIR/$UNIT" ]]; then
    cp "$TMPDIR/$UNIT" "$SYSTEMD_SYSTEM/$UNIT"
    ok "Installed $UNIT → $SYSTEMD_SYSTEM/"
  else
    warn "$UNIT not in archive — skipping"
  fi
done

# Reload and enable system units
systemctl daemon-reload

for UNIT in mcp-interceptor.service fello-webhook.service; do
  if [[ -f "$SYSTEMD_SYSTEM/$UNIT" ]]; then
    systemctl enable "$UNIT" 2>/dev/null && ok "Enabled $UNIT"
    systemctl start "$UNIT" 2>/dev/null && ok "Started $UNIT" || warn "$UNIT failed to start (check logs: journalctl -u $UNIT)"
  fi
done

# ── User unit (hermes-gateway) ────────────────────────────────────────────────

if [[ -f "$TMPDIR/hermes-gateway.service" ]]; then
  mkdir -p "$SYSTEMD_USER"
  cp "$TMPDIR/hermes-gateway.service" "$SYSTEMD_USER/hermes-gateway.service"
  ok "Installed hermes-gateway.service → $SYSTEMD_USER/"

  # Requires lingering enabled so user service survives logout
  if ! loginctl show-user root 2>/dev/null | grep -q "Linger=yes"; then
    loginctl enable-linger root
    ok "Enabled lingering for root"
  fi

  systemctl --user daemon-reload
  systemctl --user enable hermes-gateway.service 2>/dev/null && ok "Enabled hermes-gateway"
  # Note: hermes-gateway needs state restored (step 05) before it can start cleanly
  echo "  ↳ hermes-gateway.service enabled — start after step 05 (state restore)"
else
  warn "hermes-gateway.service not in archive"
fi

# ── omni-backup timer (if present) ────────────────────────────────────────────

for UNIT in omni-backup.service omni-backup.timer; do
  if [[ -f "$TMPDIR/$UNIT" ]]; then
    cp "$TMPDIR/$UNIT" "$SYSTEMD_SYSTEM/$UNIT"
    ok "Installed $UNIT"
  fi
done

if [[ -f "$SYSTEMD_SYSTEM/omni-backup.timer" ]]; then
  systemctl daemon-reload
  systemctl enable --now omni-backup.timer && ok "omni-backup.timer enabled"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "SERVICES RESTORE COMPLETE"
echo "  systemctl status mcp-interceptor fello-webhook"
echo "Next step: bash 04-infra.sh $BACKUP_DIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
