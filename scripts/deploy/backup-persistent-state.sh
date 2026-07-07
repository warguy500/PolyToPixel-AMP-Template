#!/usr/bin/env bash
set -euo pipefail

DATA_ROOT="${SPRITESMITH_DATA_ROOT:-/workspace/spritesmith-data}"
CACHE_ROOT="${SPRITESMITH_CACHE_ROOT:-/workspace/spritesmith-cache}"
BACKUP_ROOT="${SPRITESMITH_BACKUP_DEST_ROOT:-/workspace/polytopixel-backups}"
STAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
ARCHIVE_NAME="polytopixel-state-${STAMP}.tar.gz"
TEMP_ARCHIVE="${BACKUP_ROOT}/.${ARCHIVE_NAME}.tmp"
FINAL_ARCHIVE="${BACKUP_ROOT}/${ARCHIVE_NAME}"
SHA_PATH="${FINAL_ARCHIVE}.sha256"

is_subpath() {
  local child="${1//\\//}"
  local parent="${2//\\//}"
  case "$child" in
    "$parent") return 0 ;;
    "$parent"/*) return 0 ;;
    *) return 1 ;;
  esac
}

if is_subpath "$BACKUP_ROOT" "$DATA_ROOT" || is_subpath "$BACKUP_ROOT" "$CACHE_ROOT"; then
  echo "Backup destination must not overlap persistent data roots." >&2
  exit 1
fi

mkdir -p "$BACKUP_ROOT"

TAR_ITEMS=()
if [[ -d "$DATA_ROOT" ]]; then
  TAR_ITEMS+=("$(basename "$DATA_ROOT")")
fi
if [[ -d "$CACHE_ROOT" && "$CACHE_ROOT" != "$DATA_ROOT" ]]; then
  TAR_ITEMS+=("$(basename "$CACHE_ROOT")")
fi

if [[ "${#TAR_ITEMS[@]}" -eq 0 ]]; then
  echo "No persistent directories found to archive." >&2
  exit 1
fi

EXCLUDES=(
  "--exclude=$(basename "$DATA_ROOT")/backups"
  "--exclude=$(basename "$DATA_ROOT")/backups/*"
  "--exclude=$(basename "$DATA_ROOT")/tmp/*"
  "--exclude=*.pem"
  "--exclude=*.key"
  "--exclude=*.env"
  "--exclude=cloudflare-tunnel-token"
  "--exclude=*.token"
)

tar -czf "$TEMP_ARCHIVE" \
  "${EXCLUDES[@]}" \
  -C "$(dirname "$DATA_ROOT")" \
  "${TAR_ITEMS[@]}"

if ! gzip -t "$TEMP_ARCHIVE"; then
  rm -f "$TEMP_ARCHIVE"
  echo "Backup archive failed gzip verification." >&2
  exit 1
fi

if ! tar -tzf "$TEMP_ARCHIVE" >/dev/null; then
  rm -f "$TEMP_ARCHIVE"
  echo "Backup archive failed tar listing verification." >&2
  exit 1
fi

mv -f "$TEMP_ARCHIVE" "$FINAL_ARCHIVE"
sha256sum "$FINAL_ARCHIVE" | awk '{print $1}' > "$SHA_PATH"

echo "Backup written to $FINAL_ARCHIVE"
echo "SHA-256 sidecar written to $SHA_PATH"
