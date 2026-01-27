#!/usr/bin/env bash

# One-click Docker deploy for AutoCoder on a VPS with DuckDNS + Traefik + Let's Encrypt.
# Prompts for domain, DuckDNS token, email, repo, branch, and target install path.

set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run as root (sudo)." >&2
  exit 1
fi

is_truthy() {
  case "${1,,}" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

# Automation switches for CI/CD usage
AUTOMATED_MODE=0
ASSUME_YES_MODE=0
CLEANUP_REQUESTED=0
CLEANUP_VOLUMES_REQUESTED=0

if is_truthy "${AUTOCODER_AUTOMATED:-0}"; then
  AUTOMATED_MODE=1
fi
if is_truthy "${AUTOCODER_ASSUME_YES:-0}"; then
  ASSUME_YES_MODE=1
fi
if is_truthy "${AUTOCODER_CLEANUP:-0}"; then
  CLEANUP_REQUESTED=1
fi
if is_truthy "${AUTOCODER_CLEANUP_VOLUMES:-0}"; then
  CLEANUP_VOLUMES_REQUESTED=1
fi

prompt_required() {
  local var_name="$1"
  local prompt_msg="$2"
  local value=""

  # Allow pre-seeding via environment variables in automated runs.
  if [[ -n "${!var_name:-}" ]]; then
    export "${var_name}"
    return
  fi

  if [[ "${AUTOMATED_MODE}" -eq 1 ]]; then
    echo "Missing required environment variable: ${var_name}" >&2
    exit 1
  fi

  while true; do
    read -r -p "${prompt_msg}: " value
    if [[ -n "${value}" ]]; then
      printf -v "${var_name}" "%s" "${value}"
      export "${var_name}"
      return
    fi
    echo "Value cannot be empty."
  done
}

derive_duckdns_subdomain() {
  # DuckDNS expects only the subdomain (e.g., "myapp"), but users often
  # provide the full domain (e.g., "myapp.duckdns.org"). This supports both.
  if [[ "${DOMAIN}" == *.duckdns.org ]]; then
    DUCKDNS_SUBDOMAIN="${DOMAIN%.duckdns.org}"
  else
    DUCKDNS_SUBDOMAIN="${DOMAIN}"
  fi
  export DUCKDNS_SUBDOMAIN
}

confirm_yes() {
  local prompt_msg="$1"
  local reply=""

  if [[ "${ASSUME_YES_MODE}" -eq 1 ]]; then
    return 0
  fi
  if [[ "${AUTOMATED_MODE}" -eq 1 ]]; then
    return 1
  fi

  read -r -p "${prompt_msg} [y/N]: " reply
  [[ "${reply,,}" == "y" ]]
}

echo "=== AutoCoder VPS Deploy (Docker + Traefik + DuckDNS + Let's Encrypt) ==="
echo "This will install Docker, configure DuckDNS, and deploy via docker compose."
echo

prompt_required DOMAIN "Enter your DuckDNS domain (e.g., myapp.duckdns.org)"
prompt_required DUCKDNS_TOKEN "Enter your DuckDNS token"
prompt_required LETSENCRYPT_EMAIL "Enter email for Let's Encrypt notifications"

derive_duckdns_subdomain

if [[ -z "${REPO_URL:-}" ]]; then
  if [[ "${AUTOMATED_MODE}" -eq 0 ]]; then
    read -r -p "Git repo URL [https://github.com/heidi-dang/autocoder.git]: " REPO_URL
  fi
fi
REPO_URL=${REPO_URL:-https://github.com/heidi-dang/autocoder.git}

if [[ -z "${DEPLOY_BRANCH:-}" ]]; then
  if [[ "${AUTOMATED_MODE}" -eq 0 ]]; then
    read -r -p "Git branch to deploy [main]: " DEPLOY_BRANCH
  fi
fi
DEPLOY_BRANCH=${DEPLOY_BRANCH:-main}

if [[ -z "${APP_DIR:-}" ]]; then
  if [[ "${AUTOMATED_MODE}" -eq 0 ]]; then
    read -r -p "Install path [/opt/autocoder]: " APP_DIR
  fi
fi
APP_DIR=${APP_DIR:-/opt/autocoder}

if [[ -z "${APP_PORT:-}" ]]; then
  if [[ "${AUTOMATED_MODE}" -eq 0 ]]; then
    read -r -p "App internal port (container) [8888]: " APP_PORT
  fi
fi
APP_PORT=${APP_PORT:-8888}

echo
echo "Domain:          ${DOMAIN}"
echo "DuckDNS domain:  ${DUCKDNS_SUBDOMAIN}"
echo "Repo:            ${REPO_URL}"
echo "Branch:          ${DEPLOY_BRANCH}"
echo "Path:            ${APP_DIR}"
echo "App port:        ${APP_PORT}"
echo
if ! confirm_yes "Proceed?"; then
  echo "Aborted."
  exit 1
fi

ensure_packages() {
  echo
  echo "==> Installing Docker & prerequisites..."
  apt-get update -y
  apt-get install -y ca-certificates curl git gnupg

  install -m 0755 -d /etc/apt/keyrings
  if [[ ! -f /etc/apt/keyrings/docker.gpg ]]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
      | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "${VERSION_CODENAME}") stable" \
      > /etc/apt/sources.list.d/docker.list
    apt-get update -y
  fi

  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
}

configure_duckdns() {
  echo
  echo "==> Configuring DuckDNS..."
  local cron_file="/etc/cron.d/duckdns"
  cat > "${cron_file}" <<EOF
*/5 * * * * root curl -fsS "https://www.duckdns.org/update?domains=${DUCKDNS_SUBDOMAIN}&token=${DUCKDNS_TOKEN}&ip=" >/var/log/duckdns.log 2>&1
EOF
  chmod 644 "${cron_file}"

  # Run once immediately.
  curl -fsS "https://www.duckdns.org/update?domains=${DUCKDNS_SUBDOMAIN}&token=${DUCKDNS_TOKEN}&ip=" \
    >/var/log/duckdns.log 2>&1 || true
}

clone_repo() {
  echo
  echo "==> Preparing repository..."
  if [[ -d "${APP_DIR}/.git" ]]; then
    echo "Repo already exists, pulling latest..."
    git -C "${APP_DIR}" fetch --all --prune
    git -C "${APP_DIR}" checkout "${DEPLOY_BRANCH}"
    git -C "${APP_DIR}" pull --ff-only origin "${DEPLOY_BRANCH}"
  else
    echo "Cloning repository..."
    mkdir -p "${APP_DIR}"
    git clone --branch "${DEPLOY_BRANCH}" "${REPO_URL}" "${APP_DIR}"
  fi
}

assert_compose_files() {
  echo
  echo "==> Validating compose files..."
  if [[ ! -f "${APP_DIR}/docker-compose.yml" ]]; then
    echo "Missing ${APP_DIR}/docker-compose.yml" >&2
    exit 1
  fi
  if [[ ! -f "${APP_DIR}/docker-compose.traefik.yml" ]]; then
    echo "Missing ${APP_DIR}/docker-compose.traefik.yml" >&2
    exit 1
  fi
}

preserve_env_file() {
  echo
  echo "==> Checking for production .env..."
  ENV_PRESENT=0
  ENV_BACKUP=""

  if [[ -d "${APP_DIR}" && -f "${APP_DIR}/.env" ]]; then
    ENV_PRESENT=1
    ENV_BACKUP="${APP_DIR}/.env.production.bak"
    cp -f "${APP_DIR}/.env" "${ENV_BACKUP}"
    chmod 600 "${ENV_BACKUP}" || true
    echo "Found existing .env. Backed it up to ${ENV_BACKUP} and will preserve it."
  else
    echo "No existing .env found in ${APP_DIR}."
  fi
}

verify_env_preserved() {
  if [[ "${ENV_PRESENT:-0}" -eq 1 && ! -f "${APP_DIR}/.env" ]]; then
    echo "ERROR: .env was removed during deployment. Restoring from backup." >&2
    if [[ -n "${ENV_BACKUP:-}" && -f "${ENV_BACKUP}" ]]; then
      cp -f "${ENV_BACKUP}" "${APP_DIR}/.env"
      chmod 600 "${APP_DIR}/.env" || true
    fi
    exit 1
  fi

  if git -C "${APP_DIR}" ls-files --error-unmatch .env >/dev/null 2>&1; then
    echo "WARNING: .env appears to be tracked by git. Consider untracking it." >&2
  fi
}

write_env() {
  echo
  echo "==> Writing deploy env (.env.deploy)..."
  cat > "${APP_DIR}/.env.deploy" <<EOF
DOMAIN=${DOMAIN}
LETSENCRYPT_EMAIL=${LETSENCRYPT_EMAIL}
APP_PORT=${APP_PORT}
EOF
  echo "DuckDNS token stored in /etc/cron.d/duckdns (not in repo)."
}

prepare_ssl_storage() {
  echo
  echo "==> Preparing Let's Encrypt storage..."
  mkdir -p "${APP_DIR}/letsencrypt"
  touch "${APP_DIR}/letsencrypt/acme.json"
  chmod 600 "${APP_DIR}/letsencrypt/acme.json"
}

run_compose() {
  echo
  echo "==> Bringing up stack with Traefik reverse proxy and TLS..."
  cd "${APP_DIR}"

  docker network inspect traefik-proxy >/dev/null 2>&1 || docker network create traefik-proxy

  docker compose \
    --env-file .env.deploy \
    -f docker-compose.yml \
    -f docker-compose.traefik.yml \
    pull || true

  docker compose \
    --env-file .env.deploy \
    -f docker-compose.yml \
    -f docker-compose.traefik.yml \
    up -d --build
}

cleanup_vps_safe() {
  echo
  echo "==> Optional VPS cleanup (safe scope only)..."
  echo "This will prune unused Docker artifacts, clean apt caches, and trim old logs."
  echo "It will NOT delete arbitrary files and will not touch ${APP_DIR}/.env."

  if [[ "${AUTOMATED_MODE}" -eq 1 ]]; then
    if [[ "${CLEANUP_REQUESTED}" -ne 1 ]]; then
      echo "Skipping cleanup in automated mode."
      return
    fi
    echo "Cleanup requested in automated mode."
  else
    if ! confirm_yes "Run safe cleanup now?"; then
      echo "Skipping cleanup."
      return
    fi
  fi

  if command -v docker >/dev/null 2>&1; then
    echo "--> Pruning unused Docker containers/images/build cache..."
    docker container prune -f || true
    docker image prune -f || true
    docker builder prune -f || true

    if [[ "${AUTOMATED_MODE}" -eq 1 ]]; then
      if [[ "${CLEANUP_VOLUMES_REQUESTED}" -eq 1 ]]; then
        docker volume prune -f || true
      else
        echo "Skipping Docker volume prune in automated mode."
      fi
    elif confirm_yes "Also prune unused Docker volumes? (may delete data)"; then
      docker volume prune -f || true
    else
      echo "Skipping Docker volume prune."
    fi
  fi

  echo "--> Cleaning apt caches..."
  apt-get autoremove -y || true
  apt-get autoclean -y || true

  if command -v journalctl >/dev/null 2>&1; then
    echo "--> Trimming systemd journal logs older than 14 days..."
    journalctl --vacuum-time=14d || true
  fi
}

post_checks() {
  echo
  echo "==> Post-deploy checks (non-fatal)..."
  cd "${APP_DIR}"

  docker compose -f docker-compose.yml -f docker-compose.traefik.yml ps || true

  # These checks may fail briefly while the certificate is being issued.
  curl -fsS "http://${DOMAIN}/api/health" >/dev/null 2>&1 && \
    echo "Health check over HTTP: OK" || \
    echo "Health check over HTTP: not ready yet"

  curl -fsS "https://${DOMAIN}/api/health" >/dev/null 2>&1 && \
    echo "Health check over HTTPS: OK" || \
    echo "Health check over HTTPS: not ready yet (TLS may still be issuing)"
}

print_notes() {
  cat <<'EOF'

Deployment complete.

If the domain does not come up immediately:
1. Ensure ports 80 and 443 are open on the VPS firewall/security group.
2. Confirm DuckDNS points to this VPS IP.
3. Check logs:
   docker compose -f docker-compose.yml -f docker-compose.traefik.yml logs -f
4. Confirm backend health locally:
   curl -fsS http://127.0.0.1:8888/api/health || true

To update later, rerun this script. It will git pull and restart.
EOF
}

ensure_packages
configure_duckdns
clone_repo
assert_compose_files
preserve_env_file
write_env
prepare_ssl_storage
run_compose
verify_env_preserved
cleanup_vps_safe
post_checks
print_notes
