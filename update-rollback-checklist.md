# PolyToPixel update and rollback checklist

## Update

1. Record current image tag and `GET /health/ready` status.
2. Run `bash scripts/deploy/backup-persistent-state.sh`.
3. Update AMP `ImageTag` to the new verified `git-<sha>` tag.
4. Restart the AMP instance (persistent bind mounts must remain attached).
5. Verify `GET http://127.0.0.1:21617/health/ready`.
6. Verify Cloudflare Access login and shared workspace projects.

## Rollback

1. Stop the AMP instance.
2. Set `ImageTag` back to the last known-good `git-<sha>` tag.
3. If data corruption is suspected, restore the pre-update backup:
   ```bash
   python scripts/deploy/restore-migration-archive.py /workspace/polytopixel-backups/<archive>.tar.gz --apply
   ```
4. Restart and re-run health and session checks.

## Known limitations (Pass 0.093)

- Worker routing contract is defined but remote execution is not implemented
- RunPod fallback orchestration belongs to Pass 0.095
- Windows desktop worker installation belongs to Pass 0.094
