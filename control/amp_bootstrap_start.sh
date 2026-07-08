#!/usr/bin/env bash
# Pass 0.094 — AMP bootstrap: optional private release swap, then start PolyToPixel from current/.
# Template mirror of scripts/deploy/amp_bootstrap_start.sh (canonical source in repository scripts/).
set -euo pipefail

timestamp() {
	date -u +%Y-%m-%dT%H:%M:%SZ
}

resolve_deploy_root() {
	if [[ -n "${POLYTOPIXEL_DEPLOY_ROOT:-}" ]]; then
		printf '%s\n' "${POLYTOPIXEL_DEPLOY_ROOT}"
		return 0
	fi

	local script_dir
	script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
	if [[ "$(basename "${script_dir}")" == "polytopixel-bootstrap" || "$(basename "${script_dir}")" == "control" ]]; then
		cd "${script_dir}/.." && pwd
		return 0
	fi

	pwd
}

load_deploy_env_file() {
	local env_file="$1"
	[[ -f "${env_file}" ]] || return 0
	log "Loading optional overrides from ${env_file} (existing env vars are preserved)"
	while IFS= read -r raw_line || [[ -n "${raw_line}" ]]; do
		local line="${raw_line#"${raw_line%%[![:space:]]*}"}"
		line="${line%"${line##*[![:space:]]}"}"
		[[ -z "${line}" || "${line}" == \#* ]] && continue
		[[ "${line}" == export\ * ]] && line="${line#export }"
		[[ "${line}" == *"="* ]] || continue
		local key="${line%%=*}"
		key="${key#"${key%%[![:space:]]*}"}"
		key="${key%"${key##*[![:space:]]}"}"
		local value="${line#*=}"
		value="${value#"${value%%[![:space:]]*}"}"
		value="${value%"${value##*[![:space:]]}"}"
		value="${value#\"}"
		value="${value%\"}"
		value="${value#\'}"
		value="${value%\'}"
		if [[ -n "${key}" && -z "${!key:-}" ]]; then
			export "${key}=${value}"
		fi
	done < "${env_file}"
}

run_setup_server() {
	local setup_mode="$1"
	local bind_address="${SPRITESMITH_HOST:-127.0.0.1}"
	local app_port="${SPRITESMITH_PORT:-21617}"
	local health_path="${POLYTOPIXEL_HEALTH_CHECK_PATH:-/health/ready}"

	log "Entering setup holding mode (${setup_mode}) on ${bind_address}:${app_port}"
	export POLYTOPIXEL_SETUP_MODE="${setup_mode}"
	export SPRITESMITH_HOST="${bind_address}"
	export SPRITESMITH_PORT="${app_port}"
	export POLYTOPIXEL_HEALTH_CHECK_PATH="${health_path}"

	exec python3 -u - <<'PY'
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BIND = os.environ.get("SPRITESMITH_HOST", "127.0.0.1")
PORT = int(os.environ.get("SPRITESMITH_PORT", "21617"))
MODE = os.environ.get("POLYTOPIXEL_SETUP_MODE", "token_required")
HEALTH_PATH = os.environ.get("POLYTOPIXEL_HEALTH_CHECK_PATH", "/health/ready")

MESSAGES = {
    "token_required": (
        "PolyToPixel setup required.\n\n"
        "Enter the AMP setting \"GitHub Release Token\" (read-only token for private "
        "PolyToPixel release downloads), confirm the pinned Release Tag and Release Asset SHA-256, "
        "save the instance configuration, then Restart.\n"
    ),
    "deploy_failed": (
        "PolyToPixel release deploy failed and no current release is installed.\n\n"
        "Check polytopixel-bootstrap.log in the instance root, fix the GitHub Release "
        "Token, pinned Release Tag, or Release Asset SHA-256, then Restart.\n"
    ),
}


class SetupHandler(BaseHTTPRequestHandler):
    server_version = "PolyToPixelSetup/1.0"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[PolyToPixel] {self.address_string()} - {fmt % args}", flush=True)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == HEALTH_PATH or path == "/health/live":
            self._send_json(
                503,
                {
                    "status": "setup_required",
                    "mode": MODE,
                    "service": "polytopixel-setup",
                    "port": PORT,
                },
            )
            return

        message = MESSAGES.get(MODE, MESSAGES["token_required"])
        body = (
            "<!DOCTYPE html><html><head><title>PolyToPixel Setup Required</title></head>"
            f"<body><pre>{message}</pre></body></html>"
        ).encode("utf-8")
        self.send_response(503)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer((BIND, PORT), SetupHandler)
    print(f"[PolyToPixel] Setup server listening port={PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
PY
}

ROOT="$(resolve_deploy_root)"
export POLYTOPIXEL_DEPLOY_ROOT="${ROOT}"
BOOTSTRAP_DIR="${POLYTOPIXEL_BOOTSTRAP_DIR:-/opt/polytopixel-bootstrap}"
CURRENT_START="${ROOT}/current/scripts/deploy/amp_start.sh"
LOG_FILE="${ROOT}/polytopixel-bootstrap.log"
DEPLOY_SCRIPT="${BOOTSTRAP_DIR}/polytopixel_deploy_latest.py"

log() {
	echo "[$(timestamp)] $*" | tee -a "${LOG_FILE}"
}

: > "${LOG_FILE}"
log "==== PolyToPixel AMP bootstrap start ===="
log "ROOT=${ROOT}"
log "BOOTSTRAP_DIR=${BOOTSTRAP_DIR}"
log "DEPLOY_SCRIPT=${DEPLOY_SCRIPT}"
log "Token configured: $([[ -n "${POLYTOPIXEL_GITHUB_TOKEN:-}" ]] && echo yes || echo no)"

load_deploy_env_file "${ROOT}/control/deploy.env"
log "Token configured after deploy.env: $([[ -n "${POLYTOPIXEL_GITHUB_TOKEN:-}" ]] && echo yes || echo no)"

if [[ ! -f "${CURRENT_START}" && -z "${POLYTOPIXEL_GITHUB_TOKEN:-}" ]]; then
	log "No GitHub token and no current release; starting setup holding server"
	run_setup_server "token_required"
fi

UPDATER_EXIT=0
if [[ -n "${POLYTOPIXEL_GITHUB_TOKEN:-}" && -f "${DEPLOY_SCRIPT}" ]]; then
	log "Running restart-triggered deploy check"
	if python3 "${DEPLOY_SCRIPT}" --deploy --yes >> "${LOG_FILE}" 2>&1; then
		log "Deploy updater finished successfully (or already current)"
	else
		UPDATER_EXIT=$?
		log "Deploy updater failed (exit=${UPDATER_EXIT}); keeping existing current/ if present"
	fi
elif [[ -z "${POLYTOPIXEL_GITHUB_TOKEN:-}" ]]; then
	log "No GitHub token configured; skipping private release download"
else
	log "WARNING: missing ${DEPLOY_SCRIPT}; skipping auto-update"
fi

if [[ -f "${CURRENT_START}" ]]; then
	chmod +x "${CURRENT_START}" 2>/dev/null || true
	log "Starting ${CURRENT_START}"
	exec "${CURRENT_START}" "$@"
fi

if [[ -n "${POLYTOPIXEL_GITHUB_TOKEN:-}" ]]; then
	log "Deploy failed and no current release; starting setup holding server"
	run_setup_server "deploy_failed"
fi

log "No GitHub token and no current release; starting setup holding server"
run_setup_server "token_required"
