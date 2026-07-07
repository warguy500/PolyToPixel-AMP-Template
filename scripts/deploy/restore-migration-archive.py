#!/usr/bin/env python3
"""Restore PolyToPixel migration archives with integrity and safety checks (Pass 0.093)."""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

DEFAULT_DATA_ROOT = Path("/workspace/spritesmith-data")
DEFAULT_CACHE_ROOT = Path("/workspace/spritesmith-cache")
DEFAULT_BACKUP_ROOT = Path("/workspace/polytopixel-backups")

REQUIRED_DATA_ENTRIES = (
    "projects",
    "config",
)
SHARED_PROJECT_IDS = tuple(
    item.strip()
    for item in os.environ.get("POLYTOPIXEL_SHARED_PROJECT_IDS", "").split(",")
    if item.strip()
)
MIN_SHARED_PROJECT_COUNT = 3
FORBIDDEN_ARCHIVE_SUFFIXES = (".pem", ".key", ".env", ".token")
FORBIDDEN_ARCHIVE_NAMES = {
    "cloudflare-tunnel-token",
    ".env",
    "credentials.json",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore a verified PolyToPixel migration archive.")
    parser.add_argument("archive", type=Path, help="Path to polytopixel-data-*.tar.gz")
    parser.add_argument(
        "--expected-sha256",
        help="Expected SHA-256 digest for the archive (required unless --dry-run with sidecar present)",
    )
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    parser.add_argument("--staging-root", type=Path, help="Optional staging directory override")
    parser.add_argument("--dry-run", action="store_true", help="Validate archive only; do not modify active data")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Replace active persistent data after validation and pre-restore backup",
    )
    parser.add_argument(
        "--verify-shared-projects",
        action="store_true",
        help="After restore, verify the three shared studio projects are present",
    )
    return parser.parse_args()


def load_expected_sha256(archive: Path, explicit: str | None) -> str:
    if explicit:
        return explicit.strip().lower()
    sidecar = Path(f"{archive}.sha256")
    if sidecar.is_file():
        return sidecar.read_text(encoding="utf-8").strip().split()[0].lower()
    raise SystemExit("Expected SHA-256 must be provided via --expected-sha256 or a .sha256 sidecar.")


def verify_archive_digest(archive: Path, expected_sha256: str) -> None:
    actual = sha256_file(archive)
    if actual.lower() != expected_sha256.lower():
        raise SystemExit(f"Archive SHA-256 mismatch: expected {expected_sha256}, got {actual}")


def is_safe_member(name: str) -> bool:
    normalized = name.replace("\\", "/")
    if not normalized or normalized.startswith("/") or normalized.startswith("../"):
        return False
    parts = [part for part in normalized.split("/") if part]
    if ".." in parts:
        return False
    leaf = parts[-1] if parts else normalized
    if leaf in FORBIDDEN_ARCHIVE_NAMES:
        return False
    return not any(normalized.endswith(suffix) for suffix in FORBIDDEN_ARCHIVE_SUFFIXES)


def inspect_archive(archive: Path) -> list[str]:
  members: list[str] = []
  with tarfile.open(archive, mode="r:gz") as tar:
      for member in tar.getmembers():
          if not is_safe_member(member.name):
              raise SystemExit(f"Unsafe archive member rejected: {member.name}")
          members.append(member.name)
  return members


def validate_restored_layout(staging_root: Path, data_root_name: str) -> None:
    restored_data = staging_root / data_root_name
    if not restored_data.is_dir():
        raise SystemExit(f"Restored archive is missing data root directory: {restored_data}")
    for entry in REQUIRED_DATA_ENTRIES:
        if not (restored_data / entry).exists():
            raise SystemExit(f"Restored archive is missing required entry: {entry}")


def extract_to_staging(archive: Path, staging_root: Path) -> None:
    staging_root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, mode="r:gz") as tar:
        for member in tar.getmembers():
            if not is_safe_member(member.name):
                raise SystemExit(f"Unsafe archive member rejected during extraction: {member.name}")
        tar.extractall(path=staging_root)


def run_pre_restore_backup() -> None:
    backup_script = Path(__file__).resolve().parent / "backup-persistent-state.sh"
    if not backup_script.is_file():
        raise SystemExit(f"Pre-restore backup script not found: {backup_script}")
    subprocess.run(["bash", str(backup_script)], check=True)


def replace_active_data(staging_root: Path, data_root: Path, cache_root: Path) -> None:
    data_name = data_root.name
    cache_name = cache_root.name
    staged_data = staging_root / data_name
    staged_cache = staging_root / cache_name

    if staged_data.is_dir():
        if data_root.exists():
            shutil.rmtree(data_root)
        shutil.copytree(staged_data, data_root)
    if staged_cache.is_dir() and staged_cache != staged_data:
        if cache_root.exists():
            shutil.rmtree(cache_root)
        shutil.copytree(staged_cache, cache_root)


def verify_shared_projects(data_root: Path) -> None:
    projects_dir = data_root / "projects"
    if not projects_dir.is_dir():
        raise SystemExit(f"Projects directory missing after restore: {projects_dir}")
    if SHARED_PROJECT_IDS:
        missing = [project_id for project_id in SHARED_PROJECT_IDS if not (projects_dir / project_id).is_dir()]
        if missing:
            raise SystemExit(f"Shared studio projects missing after restore: {', '.join(missing)}")
        return
    project_dirs = [entry for entry in projects_dir.iterdir() if entry.is_dir()]
    if len(project_dirs) < MIN_SHARED_PROJECT_COUNT:
        raise SystemExit(
            f"Expected at least {MIN_SHARED_PROJECT_COUNT} project directories in {projects_dir}; found {len(project_dirs)}",
        )


def main() -> int:
    args = parse_args()
    archive = args.archive.resolve()
    if not archive.is_file():
        raise SystemExit(f"Archive not found: {archive}")

    expected_sha256 = load_expected_sha256(archive, args.expected_sha256)
    verify_archive_digest(archive, expected_sha256)
    inspect_archive(archive)

    if args.dry_run and not args.apply:
        print(f"DRY-RUN: archive {archive.name} validated successfully.")
        print(f"Expected SHA-256: {expected_sha256}")
        return 0

    if not args.apply:
        raise SystemExit("Refusing to modify active data without --apply. Use --dry-run for validation only.")

    staging_context = (
        tempfile.TemporaryDirectory(prefix="polytopixel-restore-")
        if args.staging_root is None
        else None
    )
    staging_root = Path(args.staging_root) if args.staging_root else Path(staging_context.name)  # type: ignore[union-attr]

    try:
        extract_to_staging(archive, staging_root)
        validate_restored_layout(staging_root, args.data_root.name)
        run_pre_restore_backup()
        replace_active_data(staging_root, args.data_root, args.cache_root)
        if args.verify_shared_projects:
            verify_shared_projects(args.data_root)
    finally:
        if staging_context is not None:
            staging_context.cleanup()

    print("Restore completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
