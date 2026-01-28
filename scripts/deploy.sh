#!/usr/bin/env bash

# One-click Docker deploy for AutoCoder on a VPS with DuckDNS + Traefik + Let's Encrypt.
# Prompts for domain, DuckDNS token, email, repo, branch, and target install path.

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root (sudo)." >&2
  exit 1
fi

prompt_required() {
  local var_name="$1" prompt_msg="$2"
  local value
  while true; do
    read -r -p "$prompt_msg: " value
    if [[ -n "$value" ]]; then
      printf -v "$var_name" '%s' "$value"
      export "$var_name"
      return
    fi
    echo "Value cannot be empty."
  done
}

echo "=== AutoCoder VPS Deploy (Docker + Traefik + DuckDNS + Let's Encrypt) ==="

prompt_required DOMAIN "Enter your DuckDNS domain (e.g., myapp.duckdns.org)"
prompt_required DUCKDNS_TOKEN "Enter your DuckDNS token"
prompt_required LETSENCRYPT_EMAIL "Enter email for Let's Encrypt notifications"

# Extract subdomain for DuckDNS API (it expects just the subdomain, not full domain)
if [[ "${DOMAIN}" == *.duckdns.org ]]; then
  DUCKDNS_SUBDOMAIN="${DOMAIN%.duckdns.org}"
else
  DUCKDNS_SUBDOMAIN="${DOMAIN}"
fi

read -r -p "Git repo URL [https://github.com/heidi-dang/autocoder.git]: " REPO_URL
REPO_URL=${REPO_URL:-https://github.com/heidi-dang/autocoder.git}

read -r -p "Git branch to deploy [main]: " DEPLOY_BRANCH
DEPLOY_BRANCH=${DEPLOY_BRANCH:-main}

read -r -p "Install path [/opt/autocoder]: " APP_DIR
APP_DIR=${APP_DIR:-/opt/autocoder}

read -r -p "App internal port (container) [8888]: " APP_PORT
APP_PORT=${APP_PORT:-8888}

echo
echo "Domain: $DOMAIN"
echo "Repo:   $REPO_URL"
echo "Branch: $DEPLOY_BRANCH"
echo "Path:   $APP_DIR"
echo
read -r -p "Proceed? [y/N]: " CONFIRM
if [[ "${CONFIRM,,}" != "y" ]]; then
  echo "Aborted."
  exit 1
fi

ensure_packages() {
  echo "Installing Docker & prerequisites..."

  # Detect OS type
  if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    OS_ID="$ID"
    OS_LIKE="${ID_LIKE:-}"
  else
    echo "ERROR: Cannot detect OS type. /etc/os-release not found."
    exit 1
  fi

  # Detect Docker distribution for repository URL
  if [[ "$OS_ID" == "debian" ]]; then
    DOCKER_DIST="debian"
  elif [[ "$OS_ID" == "ubuntu" ]]; then
    DOCKER_DIST="ubuntu"
  elif [[ "$OS_LIKE" == *"ubuntu"* ]]; then
    DOCKER_DIST="ubuntu"
  elif [[ "$OS_LIKE" == *"debian"* ]]; then
    DOCKER_DIST="debian"
  else
    DOCKER_DIST="ubuntu"
  fi

  # Check for Debian/Ubuntu family
  if [[ "$OS_ID" == "debian" || "$OS_ID" == "ubuntu" ]] || [[ "$OS_LIKE" == *"debian"* || "$OS_LIKE" == *"ubuntu"* ]]; then
    echo "Detected Debian/Ubuntu-based system, using apt-get..."
    apt-get update -y
    apt-get install -y ca-certificates curl git gnupg
    install -m 0755 -d /etc/apt/keyrings
    if [[ ! -f /etc/apt/keyrings/docker.gpg ]]; then
      curl -fsSL https://download.docker.com/linux/$DOCKER_DIST/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
      chmod a+r /etc/apt/keyrings/docker.gpg
      echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$DOCKER_DIST \
        $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
      apt-get update -y
    fi
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
  else
    echo "ERROR: Unsupported OS: $OS_ID"
    echo "This script currently supports Debian/Ubuntu-based systems only."
    echo "Please install Docker manually or add support for your distribution."
    exit 1
  fi
}

configure_duckdns() {
  echo "Configuring DuckDNS..."
  local cron_file="/etc/cron.d/duckdns"
  local token_file="/etc/duckdns_token"
  echo "$DUCKDNS_TOKEN" > "$token_file"
  chmod 600 "$token_file"
  cat > "$cron_file" <<EOF
*/5 * * * * root curl -fsS --get --data-urlencode "domains=$DUCKDNS_SUBDOMAIN" --data-urlencode "token@$token_file" --data-urlencode "ip=" "https://www.duckdns.org/update" >/var/log/duckdns.log 2>&1
EOF
  chmod 600 "$cron_file"
  # Run once immediately
  curl -fsS --get --data-urlencode "domains=$DUCKDNS_SUBDOMAIN" --data-urlencode "token@$token_file" --data-urlencode "ip=" "https://www.duckdns.org/update" >/var/log/duckdns.log 2>&1
}

clone_repo() {
  if [[ -d "$APP_DIR/.git" ]]; then
    echo "Repo already exists, pulling latest..."
    git -C "$APP_DIR" fetch --all
    git -C "$APP_DIR" checkout "$DEPLOY_BRANCH"
    git -C "$APP_DIR" pull --ff-only origin "$DEPLOY_BRANCH"
  else
    echo "Cloning repository..."
    mkdir -p "$APP_DIR"
    git clone --branch "$DEPLOY_BRANCH" "$REPO_URL" "$APP_DIR"
  fi
}

write_env() {
  echo "Writing deploy env (.env.deploy)..."
  cat > "$APP_DIR/.env.deploy" <<EOF
DOMAIN=$DOMAIN
LETSENCRYPT_EMAIL=$LETSENCRYPT_EMAIL
APP_PORT=$APP_PORT
EOF
  echo "DuckDNS token stored in /etc/cron.d/duckdns (not in repo)."
}

prepare_ssl_storage() {
  mkdir -p "$APP_DIR/letsencrypt"
  touch "$APP_DIR/letsencrypt/acme.json"
  chmod 600 "$APP_DIR/letsencrypt/acme.json"
}

run_compose() {
  echo "Bringing up stack with Traefik reverse proxy and TLS..."
  cd "$APP_DIR"
  docker network inspect traefik-proxy >/dev/null 2>&1 || docker network create traefik-proxy
  docker compose --env-file .env.deploy -f docker-compose.yml -f docker-compose.traefik.yml pull || true
  docker compose --env-file .env.deploy -f docker-compose.yml -f docker-compose.traefik.yml up -d --build
}

ensure_packages
configure_duckdns
clone_repo
write_env
prepare_ssl_storage
run_compose

echo
echo "Deployment complete."
echo "Check: http://$DOMAIN (will redirect to https after cert is issued)."
echo "Logs:  docker compose -f docker-compose.yml -f docker-compose.traefik.yml logs -f"
echo "To update: rerun this script; it will git pull and restart."
