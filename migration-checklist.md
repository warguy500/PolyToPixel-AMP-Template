# PolyToPixel AMP migration checklist

## Preconditions

- [ ] Verified image: `ghcr.io/warguy500/polytopixel:git-1eff0b915f5b9974f5f3dc3544d47e9e58375c22`
- [ ] Verified digest: `sha256:e31174946a8526aae7c34d2a805ff8788c8d3bed2e5dc24b9a9952ba4ff86cf8`
- [ ] Migration archive: `polytopixel-data-20260706T225931Z.tar.gz`
- [ ] Archive SHA-256: `14569b86e57e2a9b888cc40f141ce5cca9dfb2278ece47f9a64b656d9e4d7303`
- [ ] AMP datastore bind mounts configured before restore

## Restore procedure

1. Copy the migration archive to the AMP host (outside `spritesmith-data`).
2. Dry-run validation:
   ```bash
   python scripts/deploy/restore-migration-archive.py \
     /path/to/polytopixel-data-20260706T225931Z.tar.gz \
     --expected-sha256 14569b86e57e2a9b888cc40f141ce5cca9dfb2278ece47f9a64b656d9e4d7303 \
     --dry-run
   ```
3. Apply restore (creates pre-restore backup automatically):
   ```bash
   python scripts/deploy/restore-migration-archive.py \
     /path/to/polytopixel-data-20260706T225931Z.tar.gz \
     --expected-sha256 14569b86e57e2a9b888cc40f141ce5cca9dfb2278ece47f9a64b656d9e4d7303 \
     --apply --verify-shared-projects
   ```
4. Optional explicit project IDs:
   ```bash
   export POLYTOPIXEL_SHARED_PROJECT_IDS="project-a,project-b,project-c"
   ```

## Post-migration verification

- [ ] `GET /health/ready` returns 200
- [ ] Authenticated session lists personal and shared workspaces
- [ ] Shared workspace shows **Cart Horse Studios Shared**
- [ ] At least three shared studio projects visible (or all IDs in `POLYTOPIXEL_SHARED_PROJECT_IDS`)
- [ ] Project assets open without workspace scoping errors
- [ ] Heavy-operation lease still enforces single active job on the AMP host

## Shared project verification

Record the three production shared project IDs during cutover. After restore, confirm each `spritesmith-data/projects/<project-id>/` directory exists and opens in the guided UI under the shared workspace.
