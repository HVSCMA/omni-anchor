#!/bin/bash
# OMNI-ANCHOR Restore Step 4 — Infrastructure: TLS certs, git repos, Docker, nginx
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../config.env"

BACKUP_DIR="${1:-}"
[[ -z "$BACKUP_DIR" ]] && { echo "Usage: $0 <backup-dir>"; exit 1; }
[[ -d "$BACKUP_DIR" ]] || { echo "Backup dir not found: $BACKUP_DIR"; exit 1; }

ok()   { echo "  ✓ $*"; }
warn() { echo "  ⚠ $*"; }
die()  { echo "  ✗ FATAL: $*"; exit 1; }
info() { echo "  → $*"; }

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "RESTORE STEP 4 — Infrastructure"
echo "  Backup: $(basename "$BACKUP_DIR")"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── TLS Certificates ──────────────────────────────────────────────────────────

echo "[TLS] Restoring Let's Encrypt certificates…"
if [[ -f "$BACKUP_DIR/letsencrypt.tar.gz" ]]; then
  # Stop nginx before touching certs to avoid partial reload
  docker stop nginx 2>/dev/null || true
  # Wipe and restore
  rm -rf /etc/letsencrypt
  tar -xzf "$BACKUP_DIR/letsencrypt.tar.gz" -C /
  # Verify cert
  CERT=/etc/letsencrypt/live/hvsold.com/fullchain.pem
  if [[ -f "$CERT" ]]; then
    EXPIRY=$(openssl x509 -noout -enddate -in "$CERT" 2>/dev/null | cut -d= -f2)
    ok "TLS certs restored — expires: $EXPIRY"
  else
    warn "fullchain.pem not found after restore — check archive structure"
  fi
else
  warn "letsencrypt.tar.gz not in backup — TLS must be re-issued via certbot"
  echo "    certbot certonly --dns-cloudflare --dns-cloudflare-credentials /root/.cloudflare.ini -d '*.hvsold.com' -d hvsold.com"
fi

# ── Git Repositories ──────────────────────────────────────────────────────────

echo "[Git] Restoring repositories…"

# omni-anchor repo
if git -C "$OMNI_ROOT" rev-parse --git-dir &>/dev/null 2>&1; then
  ok "$OMNI_ROOT already a git repo — pulling if remote configured"
  if git -C "$OMNI_ROOT" remote | grep -q .; then
    git -C "$OMNI_ROOT" pull 2>/dev/null && ok "omni-anchor: pulled from remote" || warn "omni-anchor: pull failed"
  fi
else
  info "omni-anchor not a git repo — clone or unarchive needed"
  if [[ -f "$BACKUP_DIR/omni-anchor.tar.gz" ]]; then
    tar -xzf "$BACKUP_DIR/omni-anchor.tar.gz" -C /root/
    ok "omni-anchor extracted from archive"
  else
    warn "No omni-anchor git archive — clone from remote if available"
  fi
fi

# widget repo
if [[ -f "$BACKUP_DIR/widget.tar.gz" ]]; then
  mkdir -p "$(dirname "$WIDGET_ROOT")"
  tar -xzf "$BACKUP_DIR/widget.tar.gz" -C "$(dirname "$WIDGET_ROOT")"
  ok "Widget extracted from archive → $WIDGET_ROOT"
elif git -C "$WIDGET_ROOT" rev-parse --git-dir &>/dev/null 2>&1; then
  ok "$WIDGET_ROOT already present"
else
  warn "Widget archive not found — $WIDGET_ROOT may be empty"
fi

# ── Databases: PostgreSQL ──────────────────────────────────────────────────────

echo "[DB] Restoring PostgreSQL (DashClaw)…"
if [[ -f "$BACKUP_DIR/dashclaw-postgres.sql.gz" ]]; then
  # Start docker-compose first so DB container is available
  if [[ -f "$OMNI_ROOT/docker-compose.yml" ]]; then
    docker compose -f "$OMNI_ROOT/docker-compose.yml" up -d dashclaw-db 2>/dev/null || \
    docker-compose -f "$OMNI_ROOT/docker-compose.yml" up -d dashclaw-db 2>/dev/null || true
    info "Waiting for postgres to be ready…"
    for i in $(seq 1 20); do
      docker exec dashclaw-db-1 pg_isready -U dashclaw &>/dev/null && break || sleep 2
    done
  fi

  if docker ps --format '{{.Names}}' | grep -q dashclaw-db-1; then
    # Drop and recreate database
    docker exec dashclaw-db-1 psql -U dashclaw -c "DROP DATABASE IF EXISTS dashclaw;" 2>/dev/null || true
    docker exec dashclaw-db-1 psql -U dashclaw -c "CREATE DATABASE dashclaw;" 2>/dev/null || true
    zcat "$BACKUP_DIR/dashclaw-postgres.sql.gz" \
      | docker exec -i dashclaw-db-1 psql -U dashclaw -d dashclaw 2>/dev/null
    TABLES=$(docker exec dashclaw-db-1 psql -U dashclaw -d dashclaw -t -c \
      "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d ' ')
    ok "PostgreSQL restored — $TABLES tables"
  else
    warn "dashclaw-db-1 not running — restore postgres manually after docker-compose up"
  fi
else
  warn "dashclaw-postgres.sql.gz not in backup"
fi

# ── Redis ──────────────────────────────────────────────────────────────────────

echo "[Cache] Restoring Redis…"
if [[ -f "$BACKUP_DIR/redis-data.tar.gz" ]]; then
  REDIS_DATA=$(docker volume inspect omni-anchor_redis-data --format '{{.Mountpoint}}' 2>/dev/null || echo "")
  if [[ -n "$REDIS_DATA" && -d "$REDIS_DATA" ]]; then
    docker stop redis 2>/dev/null || true
    rm -rf "${REDIS_DATA:?}"/*
    tar -xzf "$BACKUP_DIR/redis-data.tar.gz" -C "$REDIS_DATA/"
    docker start redis 2>/dev/null || true
    ok "Redis data restored"
  else
    warn "Redis volume not found — will start fresh"
  fi
else
  ok "No Redis backup — will start with empty cache (safe)"
fi

# ── Docker Compose (all services) ────────────────────────────────────────────

echo "[Docker] Starting all services…"
if [[ -f "$OMNI_ROOT/docker-compose.yml" ]]; then
  docker compose -f "$OMNI_ROOT/docker-compose.yml" up -d 2>/dev/null || \
  docker-compose -f "$OMNI_ROOT/docker-compose.yml" up -d 2>/dev/null
  sleep 3
  RUNNING=$(docker ps --format '{{.Names}}' | tr '\n' ' ')
  ok "Docker containers running: $RUNNING"
else
  warn "docker-compose.yml not found at $OMNI_ROOT — start containers manually"
fi

# ── nginx validation and restart ──────────────────────────────────────────────

echo "[nginx] Validating config and restarting…"
if docker ps --format '{{.Names}}' | grep -q nginx; then
  docker exec nginx nginx -t 2>/dev/null && ok "nginx config valid" || warn "nginx config invalid — check $OMNI_ROOT/nginx/nginx.conf"
  docker restart nginx && ok "nginx restarted"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "INFRA RESTORE COMPLETE"
echo "  Containers: $(docker ps --format '{{.Names}}' | tr '\n' ' ')"
echo "Next step: bash 05-state.sh $BACKUP_DIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
