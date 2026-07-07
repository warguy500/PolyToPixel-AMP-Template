# AMP persistent storage mapping

PolyToPixel persistent state must survive container image replacement. AMP instance datastore directories bind into the container at the same paths used by the RunPod pilot.

## Required bind mounts

| Host (AMP instance datastore) | Container path | Contents |
| --- | --- | --- |
| `<instance>/spritesmith-data` | `/workspace/spritesmith-data` | Projects, config, logs, telemetry, tmp |
| `<instance>/spritesmith-cache` | `/workspace/spritesmith-cache` | Blender, Hugging Face, Torch, XDG caches |
| `<instance>/polytopixel-backups` | `/workspace/polytopixel-backups` | Backup archives and SHA-256 sidecars |

## In-container layout

```
/workspace/spritesmith-data/
  projects/
  config/
  logs/
  telemetry/
  tmp/
/workspace/spritesmith-cache/
/workspace/polytopixel-backups/
```

Legacy `spritesmith-data/backups/` is no longer the primary backup destination. Pass 0.093 writes backups to `/workspace/polytopixel-backups` to avoid recursive self-archiving.

## Update and recreate safety

1. Never store backup archives inside `spritesmith-data` or `spritesmith-cache`.
2. Configure AMP instance updates to preserve the three datastore directories above.
3. Run `scripts/deploy/backup-persistent-state.sh` before image tag changes.
4. Validate `GET /health/ready` after the new image starts.

## Migration archive reference

Verified migration archive for the current production move:

- File: `polytopixel-data-20260706T225931Z.tar.gz`
- SHA-256: `14569b86e57e2a9b888cc40f141ce5cca9dfb2278ece47f9a64b656d9e4d7303`

Restore with `scripts/deploy/restore-migration-archive.py` using `--dry-run` first, then `--apply`.
