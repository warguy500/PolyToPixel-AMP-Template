#!/usr/bin/env python3
"""Pass 0.094 — fetch, validate, and swap private PolyToPixel release bundles into current/."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # Windows local verification
    fcntl = None  # type: ignore[assignment,misc]

SCRIPT_PATH = Path(__file__).resolve()
DEFAULT_OWNER = "warguy500"
DEFAULT_REPO = "PolyToPixel"
DEFAULT_HEALTH_PATH = "/health/ready"
ASSET_NAME = "polytopixel_release.zip"
BUNDLE_DIR_NAME = "polytopixel_release"
MANIFEST_FILENAME = "release_manifest.json"
CHECKSUMS_FILENAME = "checksums.sha256"
STATE_FILENAME = ".polytopixel_deploy_state.json"
LOCK_FILENAME = ".polytopixel_deploy.lock"
GITHUB_API_VERSION = "2022-11-28"
USER_AGENT = "polytopixel-amp-deploy/1.0"
RELEASE_TAG_RE = re.compile(r"^git-[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_REL_PATHS = (
    "scripts/deploy/amp_start.sh",
    "scripts/deploy/pod_supervisor.py",
    "apps/server/app/main.py",
    "apps/server/app/static/index.html",
    MANIFEST_FILENAME,
    CHECKSUMS_FILENAME,
)

EXECUTABLE_REL_PATHS = (
    "scripts/deploy/amp_start.sh",
)

SENSITIVE_ENV_KEYS = frozenset(
    {
        "polytopixel_github_token",
        "github_token",
        "authorization",
        "token",
        "cloudflare_tunnel_token",
    }
)


class DeployError(Exception):
    """Fatal deploy error."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def log(message: str) -> None:
    safe = message
    for key in SENSITIVE_ENV_KEYS:
        token = os.environ.get(key.upper(), "") or os.environ.get(key, "")
        if token and token in safe:
            safe = safe.replace(token, "<redacted>")
    print(safe, flush=True)


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def load_deploy_env_file(path: Path) -> None:
    if not path.is_file():
        return
    log(f"Loading config: {path}")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_deploy_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env_root = os.environ.get("POLYTOPIXEL_DEPLOY_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()
    bootstrap_dir = SCRIPT_PATH.parent
    if bootstrap_dir.name in {"polytopixel-bootstrap", "control"}:
        return bootstrap_dir.parent.resolve()
    return Path.cwd().resolve()


def load_config(args: argparse.Namespace) -> dict[str, Any]:
    deploy_root = resolve_deploy_root(args.deploy_root)
    load_deploy_env_file(deploy_root / "control" / "deploy.env")

    owner = os.environ.get("POLYTOPIXEL_GITHUB_OWNER", DEFAULT_OWNER).strip() or DEFAULT_OWNER
    repo_name = os.environ.get("POLYTOPIXEL_GITHUB_REPO", DEFAULT_REPO).strip() or DEFAULT_REPO
    token = os.environ.get("POLYTOPIXEL_GITHUB_TOKEN", "").strip()
    tag = (args.tag or os.environ.get("POLYTOPIXEL_RELEASE_TAG", "")).strip()
    expected_sha256 = os.environ.get("POLYTOPIXEL_RELEASE_ZIP_SHA256", "").strip().lower()
    port = os.environ.get("SPRITESMITH_PORT", "21617").strip() or "21617"
    health_path = os.environ.get("POLYTOPIXEL_HEALTH_CHECK_PATH", DEFAULT_HEALTH_PATH).strip() or DEFAULT_HEALTH_PATH

    if args.local_zip:
        # Local-zip installs are used for CI and offline verification. They must not require pinned
        # GitHub release identity or an expected outer checksum, because the zip is already local.
        expected_sha256 = ""
        if not tag:
            tag = "git-local-zip"
    elif not tag:
        raise DeployError(
            "POLYTOPIXEL_RELEASE_TAG is required for production AMP deploys. "
            "Set the AMP setting \"Release Tag Override\" to git-<full-sha>."
        )
    if tag.lower() in {"latest", "current", "stable"}:
        raise DeployError("Mutable release tags are forbidden; set POLYTOPIXEL_RELEASE_TAG to git-<full-sha>.")
    if not args.local_zip and RELEASE_TAG_RE.fullmatch(tag) is None:
        raise DeployError(f"Release tag must match git-<40-hex-sha>, got {tag!r}.")

    if not args.local_zip and not expected_sha256:
        raise DeployError(
            "POLYTOPIXEL_RELEASE_ZIP_SHA256 is required for production AMP deploys. "
            "Set the AMP setting \"Release Asset SHA-256\" to the expected 64-hex checksum."
        )
    if not args.local_zip and SHA256_RE.fullmatch(expected_sha256) is None:
        raise DeployError(f"POLYTOPIXEL_RELEASE_ZIP_SHA256 must be 64 lowercase hex characters, got {expected_sha256!r}.")

    return {
        "deploy_root": deploy_root,
        "github_owner": owner,
        "github_repo": repo_name,
        "github_repo_slug": f"{owner}/{repo_name}",
        "github_token": token,
        "release_tag": tag,
        "expected_zip_sha256": expected_sha256,
        "health_url": f"http://127.0.0.1:{port}{health_path}",
        "auto_confirm": args.yes or env_bool("POLYTOPIXEL_AUTO_CONFIRM", False),
        "keep_backups": env_bool("POLYTOPIXEL_KEEP_BACKUPS", True),
        "check_only": args.check_only,
        "dry_run": args.dry_run,
        "deploy": args.deploy,
    }


def github_request(
    url: str,
    token: str,
    accept: str = "application/vnd.github+json",
    timeout: float = 60.0,
) -> tuple[int, dict[str, str], bytes]:
    headers = {
        "Accept": accept,
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": USER_AGENT,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            response_headers = {k.lower(): v for k, v in response.headers.items()}
            return response.status, response_headers, body
    except urllib.error.HTTPError as exc:
        body = exc.read()
        response_headers = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
        return exc.code, response_headers, body


def parse_github_json(body: bytes) -> dict[str, Any]:
    parsed = json.loads(body.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise DeployError("GitHub API returned non-object JSON.")
    return parsed


def fetch_release(repo_slug: str, token: str, tag: str) -> dict[str, Any]:
    if not tag:
        raise DeployError("release tag is required; latest-release resolution is forbidden in production")
    url = f"https://api.github.com/repos/{repo_slug}/releases/tags/{tag}"
    log(f"Querying GitHub release tag: {repo_slug}@{tag}")

    if not token:
        log("WARNING: POLYTOPIXEL_GITHUB_TOKEN is not set. Private release download will likely fail.")

    status, headers, body = github_request(url, token)
    if status in (401, 403):
        raise DeployError(
            f"GitHub auth failed ({status}). "
            "Set the AMP GitHub Release Token field or POLYTOPIXEL_GITHUB_TOKEN."
        )
    if status == 404:
        raise DeployError(f"Release not found or repo inaccessible: {repo_slug} ({status}).")
    if status != 200:
        detail = body.decode("utf-8", errors="replace")[:300]
        raise DeployError(f"GitHub API error {status}: {detail}")

    remaining = headers.get("x-ratelimit-remaining")
    if remaining is not None:
        log(f"GitHub rate limit remaining: {remaining}")

    release = parse_github_json(body)
    if release.get("draft"):
        raise DeployError("Release is a draft; refusing to deploy.")
    return release


def find_asset(release: dict[str, Any], asset_name: str) -> dict[str, Any]:
    assets = release.get("assets", [])
    if not isinstance(assets, list):
        raise DeployError("Release assets missing or invalid.")
    for asset in assets:
        if isinstance(asset, dict) and asset.get("name") == asset_name:
            return asset
    raise DeployError(f"Release asset {asset_name!r} not found.")


def download_release_asset(
    repo_slug: str,
    asset: dict[str, Any],
    token: str,
    dest_path: Path,
) -> None:
    asset_id = asset.get("id")
    if asset_id is None:
        raise DeployError(f"Asset {asset.get('name', '?')} missing id.")

    partial_path = dest_path.with_suffix(dest_path.suffix + ".partial")
    partial_path.parent.mkdir(parents=True, exist_ok=True)
    if partial_path.exists():
        partial_path.unlink()

    url = f"https://api.github.com/repos/{repo_slug}/releases/assets/{asset_id}"
    log(f"Downloading asset {asset.get('name')} -> {dest_path.name}")
    status, _, body = github_request(url, token, accept="application/octet-stream", timeout=300.0)
    if status != 200:
        detail = body.decode("utf-8", errors="replace")[:300]
        raise DeployError(f"Asset download failed ({status}): {detail}")

    partial_path.write_bytes(body)
    os.replace(partial_path, dest_path)
    log(f"Download complete: {dest_path.name} ({dest_path.stat().st_size} bytes)")


def verify_outer_zip_sha256(zip_path: Path, expected_sha256: str) -> str:
    expected = expected_sha256.strip().lower()
    if SHA256_RE.fullmatch(expected) is None:
        raise DeployError("expected outer ZIP SHA-256 is missing or malformed")
    actual = sha256_file(zip_path)
    log(f"Outer ZIP SHA-256 expected={expected} actual={actual}")
    if actual != expected:
        raise DeployError("Outer ZIP SHA-256 mismatch; refusing to extract or activate bundle.")
    return actual


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_checksums_file(content: str) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for line_no, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise DeployError(f"Invalid checksum line {line_no}.")
        digest, rel_path = parts[0].strip().lower(), parts[1].strip().replace("\\", "/")
        if len(digest) != 64:
            raise DeployError(f"Invalid SHA256 on checksum line {line_no}.")
        checksums[rel_path] = digest
    return checksums


def sanitize_manifest(raw: dict[str, Any]) -> dict[str, Any]:
    required = [
        "schema_version",
        "release_channel",
        "commit",
        "short_commit",
        "build_number",
        "built_at_utc",
        "source_date_epoch",
        "source",
        "identity",
    ]
    missing = [key for key in required if key not in raw]
    if missing:
        raise DeployError(f"Manifest missing keys: {', '.join(missing)}")
    if int(raw.get("schema_version", 0)) != 1:
        raise DeployError("Manifest schema_version must be 1.")
    manifest = {key: str(raw.get(key, "")).strip() for key in required}
    identity = manifest.get("identity", "")
    commit = manifest.get("commit", "")
    if identity != f"git-{commit}":
        raise DeployError("Manifest identity does not match commit; refusing to deploy.")
    return manifest


def chmod_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | 0o111)


def validate_bundle_root(bundle_root: Path) -> dict[str, Any]:
    if bundle_root.name != BUNDLE_DIR_NAME:
        raise DeployError(f"Expected top-level folder {BUNDLE_DIR_NAME}/, got {bundle_root.name!r}.")

    for rel in REQUIRED_REL_PATHS:
        candidate = bundle_root / rel
        if not candidate.is_file():
            raise DeployError(f"Missing required file: {rel}")

    manifest_path = bundle_root / MANIFEST_FILENAME
    manifest_raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest_raw, dict):
        raise DeployError(f"{MANIFEST_FILENAME} must be a JSON object.")
    manifest = sanitize_manifest(manifest_raw)

    checksums_path = bundle_root / CHECKSUMS_FILENAME
    checksum_map = parse_checksums_file(checksums_path.read_text(encoding="utf-8"))
    if not checksum_map:
        raise DeployError(f"{CHECKSUMS_FILENAME} contains no entries.")

    bundle_files: dict[str, Path] = {}
    for file_path in sorted(bundle_root.rglob("*")):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(bundle_root).as_posix()
        if rel == CHECKSUMS_FILENAME:
            continue
        bundle_files[rel] = file_path

    for rel_path, expected in sorted(checksum_map.items()):
        file_path = bundle_root / Path(*rel_path.split("/"))
        if not file_path.is_file():
            raise DeployError(f"Checksum entry missing file: {rel_path}")
        actual = sha256_file(file_path)
        if actual != expected:
            raise DeployError(f"Checksum mismatch for {rel_path}")

    for rel_path in sorted(bundle_files.keys()):
        if rel_path not in checksum_map:
            raise DeployError(f"Bundle file missing from checksums: {rel_path}")

    for rel in EXECUTABLE_REL_PATHS:
        chmod_executable(bundle_root / rel)

    log(
        "Validated release metadata: "
        f"tag channel={manifest.get('release_channel')} "
        f"build={manifest.get('build_number')} "
        f"commit={manifest.get('short_commit')}@{manifest.get('commit')}"
    )
    return manifest


def extract_release_zip(zip_path: Path, extract_dir: Path) -> Path:
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(extract_dir)

    bundle_root = extract_dir / BUNDLE_DIR_NAME
    if not bundle_root.is_dir():
        raise DeployError(f"Zip did not extract to {BUNDLE_DIR_NAME}/ under {extract_dir}")
    return bundle_root


def read_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def write_state(path: Path, state: dict[str, Any]) -> None:
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8", newline="\n")


def swap_current(deploy_root: Path, staged_bundle: Path, release_tag: str, keep_backups: bool) -> Path:
    current_dir = deploy_root / "current"
    previous_root = deploy_root / "previous"
    previous_root.mkdir(parents=True, exist_ok=True)

    old_tag = "unknown"
    state = read_state(deploy_root / STATE_FILENAME)
    if state.get("deployed_tag"):
        old_tag = str(state["deployed_tag"])

    backup_name = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{old_tag}"
    backup_path = previous_root / backup_name

    if current_dir.exists():
        log(f"Backing up current -> {backup_path.name}")
        shutil.move(str(current_dir), str(backup_path))
    else:
        backup_path = Path("")

    try:
        shutil.move(str(staged_bundle), str(current_dir))
    except Exception:
        if backup_path and backup_path.exists() and not current_dir.exists():
            shutil.move(str(backup_path), str(current_dir))
        raise

    if not keep_backups and backup_path and backup_path.exists():
        shutil.rmtree(backup_path)
        backup_path = Path("")

    log(f"Activated release {release_tag} at current/")
    return backup_path


def confirm_deploy(config: dict[str, Any], release_tag: str) -> None:
    if config["auto_confirm"] or config["dry_run"] or config["check_only"]:
        return
    try:
        answer = input(f"Deploy release {release_tag} into current/? Type 'yes': ").strip().lower()
    except EOFError:
        answer = ""
    if answer != "yes":
        raise DeployError("Aborted by user (pass --yes or set POLYTOPIXEL_AUTO_CONFIRM=1).")


def install_local_zip(config: dict[str, Any], zip_path: Path, release_tag: str) -> int:
    if not zip_path.is_file():
        raise DeployError(f"Local zip not found: {zip_path}")

    staging_dir = config["deploy_root"] / "releases" / release_tag / "staging"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)

    bundle_root = extract_release_zip(zip_path, staging_dir)
    validate_bundle_root(bundle_root)

    if config["dry_run"]:
        shutil.rmtree(staging_dir, ignore_errors=True)
        log("Dry-run complete: validation succeeded; current/ unchanged.")
        return 0

    lock_path = config["deploy_root"] / LOCK_FILENAME
    with DeployLock(lock_path):
        swap_current(config["deploy_root"], bundle_root, release_tag, keep_backups=config["keep_backups"])
    return 0


class DeployLock:
    def __init__(self, path: Path):
        self.path = path
        self.handle = None

    def __enter__(self) -> DeployLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+", encoding="utf-8")
        self.handle.seek(0)
        self.handle.truncate()
        self.handle.write(f"pid={os.getpid()} started={utc_now_iso()}\n")
        self.handle.flush()
        if fcntl is not None:
            try:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise DeployError(f"Another deploy appears to be running ({self.path}).") from exc
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.handle is not None:
            if fcntl is not None:
                try:
                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
            self.handle.close()


def run(config: dict[str, Any], *, local_zip: Path | None = None) -> int:
    deploy_root: Path = config["deploy_root"]
    repo_slug: str = config["github_repo_slug"]
    token: str = config["github_token"]
    tag_override: str = config["release_tag"]
    expected_zip_sha256: str = config["expected_zip_sha256"]

    deploy_root.mkdir(parents=True, exist_ok=True)
    (deploy_root / "releases").mkdir(parents=True, exist_ok=True)
    (deploy_root / "previous").mkdir(parents=True, exist_ok=True)

    if local_zip is not None:
        release_tag = tag_override or local_zip.stem.replace("_release", "")
        return install_local_zip(config, local_zip, release_tag)

    state_path = deploy_root / STATE_FILENAME
    state = read_state(state_path)
    deployed_tag = str(state.get("deployed_tag", "")).strip()

    release = fetch_release(repo_slug, token, tag_override)
    release_tag = str(release.get("tag_name", "")).strip()
    if not release_tag:
        raise DeployError("Release missing tag_name.")

    log(f"Selected release tag: {release_tag}")
    if deployed_tag == release_tag and config["check_only"]:
        log("Already current.")
        return 0
    if deployed_tag == release_tag and not config["dry_run"] and config["deploy"]:
        log("Already current; skipping download and swap.")
        return 0

    if config["check_only"]:
        if deployed_tag == release_tag:
            log("Already current.")
        else:
            log(f"Update available: deployed={deployed_tag or '(none)'} selected={release_tag}")
        return 0

    confirm_deploy(config, release_tag)

    release_dir = deploy_root / "releases" / release_tag
    zip_path = release_dir / ASSET_NAME
    if not zip_path.is_file():
        asset = find_asset(release, ASSET_NAME)
        download_release_asset(repo_slug, asset, token, zip_path)
    else:
        log(f"Reusing cached zip: {zip_path.name}")

    verify_outer_zip_sha256(zip_path, expected_zip_sha256)

    staging_dir = release_dir / "staging"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)

    bundle_root = extract_release_zip(zip_path, staging_dir)
    manifest = validate_bundle_root(bundle_root)

    if config["dry_run"]:
        shutil.rmtree(staging_dir, ignore_errors=True)
        log("Dry-run complete: download and validation succeeded; current/ unchanged.")
        return 0

    if not config["deploy"]:
        raise DeployError("No action mode selected. Use --check-only, --dry-run, or --deploy.")

    lock_path = deploy_root / LOCK_FILENAME
    with DeployLock(lock_path):
        backup_path = swap_current(
            deploy_root,
            bundle_root,
            release_tag,
            keep_backups=config["keep_backups"],
        )

        new_state = {
            "deployed_tag": release_tag,
            "deployed_commit": manifest.get("commit", ""),
            "deployed_short_commit": manifest.get("short_commit", ""),
            "deployed_build_number": manifest.get("build_number", ""),
            "deployed_at": utc_now_iso(),
            "previous_backup_path": str(backup_path) if str(backup_path) else "",
        }
        write_state(state_path, new_state)
        log(f"Deploy state written: {state_path.name}")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PolyToPixel AMP private release deployer.")
    parser.add_argument("--deploy-root", default=None, help="AMP instance root (default: POLYTOPIXEL_DEPLOY_ROOT)")
    parser.add_argument("--check-only", action="store_true", help="Compare latest release to deployed state")
    parser.add_argument("--dry-run", action="store_true", help="Download and validate without swapping current/")
    parser.add_argument("--deploy", action="store_true", help="Download, validate, and swap into current/")
    parser.add_argument("--local-zip", default=None, help="Install from a local polytopixel_release.zip (tests/CI)")
    parser.add_argument("--tag", default=None, help="Deploy a specific GitHub release tag")
    parser.add_argument("--yes", action="store_true", help="Skip interactive confirmation")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.local_zip:
        config = load_config(args)
        config["dry_run"] = args.dry_run
        config["keep_backups"] = True
        log(f"Deploy root: {config['deploy_root']}")
        try:
            return run(config, local_zip=Path(args.local_zip))
        except DeployError as exc:
            log(f"ERROR: {exc}")
            return 1

    selected = sum(1 for flag in (args.check_only, args.dry_run, args.deploy) if flag)
    if selected != 1:
        parser.error("Specify exactly one of --check-only, --dry-run, or --deploy.")

    config = load_config(args)
    log(f"Deploy root: {config['deploy_root']}")
    log(f"GitHub repo: {config['github_repo_slug']}")
    log(f"Token configured: {'yes' if config['github_token'] else 'no'}")

    try:
        return run(config)
    except DeployError as exc:
        log(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    if sys.platform == "win32":
        log("WARNING: deploy lock uses fcntl; run on Linux/AMP host.")
    sys.exit(main())
