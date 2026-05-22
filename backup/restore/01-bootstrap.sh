#!/bin/bash
# OMNI-ANCHOR Bootstrap — installs all OS dependencies on a blank Ubuntu 24.04 VPS
# Run FIRST on a new server before any other restore step
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ok()   { echo "  ✓ $*"; }
info() { echo "  → $*"; }
die()  { echo "  ✗ FATAL: $*"; exit 1; }

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "OMNI-ANCHOR BOOTSTRAP"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

[[ $EUID -eq 0 ]] || die "Must run as root"
[[ -f /etc/os-release ]] && source /etc/os-release
[[ "${ID:-}" == "ubuntu" ]] || { echo "  ⚠ Not Ubuntu — proceeding anyway"; }

# ── System update ─────────────────────────────────────────────────────────────

info "Updating apt cache…"
apt-get update -qq

# ── Core utilities ─────────────────────────────────────────────────────────────

info "Installing core packages…"
PACKAGES=(
  curl wget git sqlite3 openssl python3 python3-pip python3-venv
  nginx certbot python3-certbot-dns-cloudflare
  build-essential ca-certificates gnupg lsb-release
  jq unzip tar gzip
)
apt-get install -y -qq "${PACKAGES[@]}" && ok "Core packages installed"

# ── Docker ────────────────────────────────────────────────────────────────────

if ! command -v docker &>/dev/null; then
  info "Installing Docker…"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable --now docker
  ok "Docker installed and started"
else
  ok "Docker already installed: $(docker --version)"
fi

# ── docker-compose standalone (v2 plugin is above; keep v1 compat symlink) ───

if ! command -v docker-compose &>/dev/null; then
  COMPOSE_VERSION="v2.27.1"
  curl -fsSL \
    "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-$(uname -m)" \
    -o /usr/local/bin/docker-compose
  chmod +x /usr/local/bin/docker-compose
  ok "docker-compose $COMPOSE_VERSION installed"
else
  ok "docker-compose already present"
fi

# ── Python / uvicorn ──────────────────────────────────────────────────────────

if ! command -v uvicorn &>/dev/null; then
  info "Installing uvicorn + fastapi…"
  pip3 install -q uvicorn fastapi httpx python-multipart
  ok "uvicorn installed"
else
  ok "uvicorn present"
fi

# ── rclone ────────────────────────────────────────────────────────────────────

if ! command -v rclone &>/dev/null; then
  info "Installing rclone…"
  curl -fsSL https://rclone.org/install.sh | bash -s -- --quiet
  ok "rclone installed"
else
  ok "rclone present: $(rclone version --check 2>&1 | head -1)"
fi

# ── Node.js (for widget build tools if needed) ────────────────────────────────

if ! command -v node &>/dev/null; then
  info "Installing Node.js 20…"
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y -qq nodejs
  ok "Node.js $(node --version) installed"
else
  ok "Node.js present: $(node --version)"
fi

# ── Kernel tuning ─────────────────────────────────────────────────────────────
# Required for Redis — prevents background save failures under memory pressure

if ! grep -q "vm.overcommit_memory" /etc/sysctl.conf 2>/dev/null; then
  echo "vm.overcommit_memory = 1" >> /etc/sysctl.conf
  sysctl vm.overcommit_memory=1 -q
  ok "vm.overcommit_memory = 1 applied"
else
  ok "vm.overcommit_memory already set"
fi

# ── Create runtime directories ────────────────────────────────────────────────

info "Creating runtime directories…"
mkdir -p /root/backups/omni-anchor
mkdir -p /root/.hermes/memories /root/.hermes/sessions
mkdir -p /root/.claude/projects/-root/memory
mkdir -p /root/.config/systemd/user
mkdir -p /var/www/widget
mkdir -p /etc/letsencrypt
ok "Runtime directories ready"

# ── Hermes agent install ──────────────────────────────────────────────────────

if ! command -v hermes &>/dev/null; then
  if pip3 show hermes-agent &>/dev/null 2>&1; then
    ok "hermes-agent already installed"
  else
    info "hermes-agent not in PATH — restore will handle via pip or git"
    echo "  ⚠ Install hermes-agent manually or via restore step after code is back"
  fi
else
  ok "hermes present: $(hermes --version 2>/dev/null || echo 'installed')"
fi

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "BOOTSTRAP COMPLETE"
echo "  Docker:    $(docker --version 2>/dev/null | cut -d' ' -f3 | tr -d ',')"
echo "  Python:    $(python3 --version 2>/dev/null)"
echo "  Node:      $(node --version 2>/dev/null)"
echo "  rclone:    $(rclone --version 2>/dev/null | head -1)"
echo ""
echo "Next step: bash 02-secrets.sh \$BACKUP_DIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
