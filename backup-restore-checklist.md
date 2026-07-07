# PolyToPixel backup and restore checklist

## Backup

- [ ] Confirm `SPRITESMITH_BACKUP_DEST_ROOT=/workspace/polytopixel-backups`
- [ ] Run `bash scripts/deploy/backup-persistent-state.sh`
- [ ] Verify archive path is **outside** `spritesmith-data` and `spritesmith-cache`
- [ ] Verify companion `.sha256` sidecar exists
- [ ] Record archive filename and digest in the deployment evidence log

## Restore (migration archive)

- [ ] Validate SHA-256 with `--dry-run`
- [ ] Apply only with `--apply` after dry-run success
- [ ] Confirm automatic pre-restore backup was created
- [ ] Run with `--verify-shared-projects` after migration

## Restore (legacy state archive)

- [ ] Use only for non-migration state archives created by the Pass 0.093 backup script
- [ ] Set `POLYTOPIXEL_RESTORE_CONFIRM=1`
- [ ] Run `bash scripts/deploy/restore-persistent-state.sh /path/to/archive.tar.gz`

## Safety rules

- Never store backup archives inside the directories being archived
- Never restore archives without SHA-256 validation for migration data
- Never include credentials, tunnel tokens, or `.env` secrets in archives
