#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 /path/to/spritesmith-state-YYYYMMDD.tar.gz" >&2
  echo "For verified migration archives use scripts/deploy/restore-migration-archive.py instead." >&2
  exit 1
fi

ARCHIVE="$1"
if [[ ! -f "$ARCHIVE" ]]; then
  echo "Archive not found: $ARCHIVE" >&2
  exit 1
fi

DATA_ROOT="${SPRITESMITH_DATA_ROOT:-/workspace/spritesmith-data}"
CACHE_ROOT="${SPRITESMITH_CACHE_ROOT:-/workspace/spritesmith-cache}"

if [[ -z "${POLYTOPIXEL_RESTORE_CONFIRM:-}" ]]; then
  echo "Refusing to restore without POLYTOPIXEL_RESTORE_CONFIRM=1" >&2
  echo "Use scripts/deploy/restore-migration-archive.py for migration archives with SHA-256 validation." >&2
  exit 1
fi

if ! gzip -t "$ARCHIVE"; then
  echo "Archive failed gzip verification." >&2
  exit 1
fi

if ! tar -tzf "$ARCHIVE" >/dev/null; then
  echo "Archive failed tar listing verification." >&2
  exit 1
fi

bash "$(dirname "$0")/backup-persistent-state.sh"

mkdir -p "$(dirname "$DATA_ROOT")"
tar -xzf "$ARCHIVE" -C "$(dirname "$DATA_ROOT")"
mkdir -p "$DATA_ROOT" "$CACHE_ROOT"
echo "Restored archive to $(dirname "$DATA_ROOT")"
