# OMNI-ANCHOR v4.3 — Disaster Recovery Runbook

**Last updated:** 2026-05-21  
**Server:** srv1532021 · KVM4 · 92.112.184.45 · Ubuntu 24.04  
**Author:** Willow / Claude  

---

## Triage — What Broke?

| Symptom | Jump to |
|---|---|
| Willow not responding on Telegram | [§5 Agent State](#5-restore-agent-state) → [§3 Services](#3-restore-systemd-services) |
| widget.hvsold.com / api.hvsold.com down | [§4 Infrastructure](#4-restore-infrastructure) |
| MCP interceptor not running | [§3 Services](#3-restore-systemd-services) |
| Total server loss / new VPS | Full sequence §1 → §6 |
| Data corruption (DB) | [§5 Agent State](#5-restore-agent-state) or [§4 Databases](#databases) |
| TLS cert errors | [§4 TLS](#tls) |

---

## Prerequisites

Before any restore step, you need:

```bash
# 1. The backup directory
BACKUP_DIR="/root/backups/omni-anchor/YYYY-MM-DD_HH-MM"  # pick the right timestamp

# 2. The encryption key (stored separately from backups)
# Key location: /root/.backup-key
# If server is lost: key was included in secrets.tar.gz.enc (chicken/egg — use last known key)
# KEEP A COPY OF /root/.backup-key OFFLINE OR IN PASSWORD MANAGER

# 3. Verify the backup before restoring
bash /root/omni-anchor/backup/validate.sh "$BACKUP_DIR"
```

---

## 1. Bootstrap (New Server)

```bash
bash /root/omni-anchor/backup/restore/01-bootstrap.sh
```

Installs: Docker, nginx, certbot, python3, uvicorn, git, rclone, sqlite3, curl.  
Run this first on a blank Ubuntu 24.04 VPS.

---

## 2. Restore Secrets

```bash
bash /root/omni-anchor/backup/restore/02-secrets.sh "$BACKUP_DIR"
```

Decrypts `secrets.tar.gz.enc` → restores:
- `/root/omni-anchor/.env`
- `/usr/local/lib/hermes-agent/.env`
- `/root/dashclaw/.env.local`

**Required before any other step.** All services depend on `.env`.

---

## 3. Restore Systemd Services

```bash
bash /root/omni-anchor/backup/restore/03-services.sh "$BACKUP_DIR"
```

Restores and enables:
- `mcp-interceptor.service`
- `fello-webhook.service`
- `hermes-gateway.service` (user service)

---

## 4. Restore Infrastructure

```bash
bash /root/omni-anchor/backup/restore/04-infra.sh "$BACKUP_DIR"
```

Restores:
- **TLS certs** → `/etc/letsencrypt/` (avoids re-issuing from Let's Encrypt)
- **Git repos** → `/root/omni-anchor/` and `/var/www/widget/`
- **Docker** → starts all containers via docker-compose
- **nginx** config validated and container restarted

---

## 5. Restore Agent State

```bash
bash /root/omni-anchor/backup/restore/05-state.sh "$BACKUP_DIR"
```

Restores:
- **ClawMem** episodic.db (Willow's memories)
- **Hermes state** — SOUL.md, config.yaml, state.db, kanban.db, memories/, sessions/
- **Claude memory** — `/root/.claude/projects/-root/memory/`

⚠️ Stop Hermes gateway before restoring state:
```bash
systemctl --user stop hermes-gateway.service
```

---

## 6. Post-Restore Verification

```bash
bash /root/omni-anchor/backup/restore/06-verify.sh
```

Checks all services are healthy and endpoints respond.

---

## Quick Reference — Critical Ports & Services

| Service | Port | Manager | Health check |
|---|---|---|---|
| MCP Interceptor | :8000 | systemd (system) | `curl localhost:8000/health` |
| Fello Webhook | :8100 | systemd (system) | `curl localhost:8100/health` |
| Hermes/Willow | — | systemd (user) | `hermes gateway status` |
| nginx | 80/443 | Docker | `docker ps` |
| redis | 6379 | Docker | `docker exec redis redis-cli ping` |
| DashClaw DB | 5433 | Docker | `docker exec dashclaw-db-1 pg_isready` |

## Critical File Locations

| What | Where |
|---|---|
| All API keys | `/root/omni-anchor/.env` |
| Hermes identity | `/root/.hermes/SOUL.md` |
| Willow memories | `/root/.hermes/memories/` + `/root/omni-anchor/.clawmem/episodic.db` |
| nginx config | `/root/omni-anchor/nginx/nginx.conf` |
| TLS certs | `/etc/letsencrypt/live/hvsold.com/` |
| Backup encryption key | `/root/.backup-key` ← **store offline copy** |

## Backup Schedule

Daily at **03:00 UTC** via `omni-backup.timer`.  
Retention: 7 daily + 4 weekly (Sundays).  
Last backup log: `/root/backups/omni-anchor/last.log`
