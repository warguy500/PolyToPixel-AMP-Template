# PolyToPixel update and rollback checklist

## Update (release-bundle model — Pass 0.094+)

1. Record current deployed release tag from `current/release_manifest.json` or `.polytopixel_deploy_state.json`.
2. Run `bash scripts/deploy/backup-persistent-state.sh` from the running instance (or host-side equivalent).
3. Publish new `polytopixel_release.zip` to private GitHub Release `git-<sha>` (CI/manual).
4. Set `ReleaseTagOverride=git-<sha>` in AMP settings (must be pinned; blank/latest is forbidden).
5. Update `ReleaseAssetSha256` to the new asset SHA-256 for that pinned release tag.
6. **Restart** the AMP instance (persistent bind mounts must remain attached).
7. Verify `GET http://127.0.0.1:21617/health/ready`.
8. Verify Cloudflare Access login and shared workspace projects.

Runtime image updates (Blender/cloudflared/Python) are separate from application zip updates and require a new `polytopixel-runtime` image tag (Pass 0.095 publication process).

## Rollback

1. Stop the AMP instance.
2. Set `ReleaseTagOverride` to the last known-good `git-<sha>` tag, update `ReleaseAssetSha256` to match, then **Restart**, **or** manually restore:
   ```bash
   mv current current-broken
   mv previous/<timestamp>-<tag> current
   ```
3. If data corruption is suspected, restore the pre-update backup:
   ```bash
   python scripts/deploy/restore-migration-archive.py /workspace/polytopixel-backups/<archive>.tar.gz --apply
   ```
4. Restart and re-run health and session checks.

## Known limitations

- Pass 0.094 prepares runtime/release split; live AMP cutover to public runtime image is Pass 0.095
- Worker routing contract is defined but remote execution is not implemented
- RunPod fallback orchestration is a later pass
- Windows desktop worker installation is a later pass
