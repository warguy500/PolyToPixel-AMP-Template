# PolyToPixel on AMP (Pass 0.093–0.098)

PolyToPixel runs on CubeCoders AMP Generic Module. Pass 0.094 splits deployment into:

- **Public runtime image:** `ghcr.io/warguy500/polytopixel-runtime` (Blender, cloudflared, bootstrap — no app code)
- **Private release zip:** `polytopixel_release.zip` on GitHub Releases (application layer)

Pass 0.098 cuts the AMP template over to the public runtime image and pins the private release bundle to an immutable tag + outer SHA-256.

## Architecture

- **AMP instance** binds localhost port **21617** with bundled **cloudflared** (enabled by default).
- **Start/Restart** runs bootstrap deploy (not AMP Update); private zip installs into `current/`.
- **Cloudflare Access** protects the public hostname. Production identity example: `polytopixel.admin@gmail.com`.
- **Shared workspace** label in the UI: `Cart Horse Studios Shared`.
- **Persistent state** survives release swaps through AMP instance datastore bind mounts.

## Template files

| File | Purpose |
| --- | --- |
| `polytopixel.kvp` | AMP Generic Module application definition |
| `polytopixelconfig.json` | AMP settings manifest |
| `polytopixelmetaconfig.json` | Maps AMP settings to `polytopixel.env` |
| `polytopixel.env` | Default instance environment template |
| `env.example` | Documented production environment variables |
| `polytopixelupdates.json` | Disables AMP Update (`[]`); deploy on Start/Restart |
| `control/` | Bootstrap script reference copies |

These files are the source for a future public `AMPTemplates` export. They contain placeholders only.

## Resource guidance

| Resource | Guidance |
| --- | --- |
| CPU | 4 cores |
| RAM | 8 GB normal, 12 GB hard ceiling |
| Disk | Reserve persistent datastore on RAID-backed storage (about 800 GB free on target host) |
| GPU | AMP CPU control plane: `SPRITESMITH_GPU_REQUIRED=false`. Server GPU is priority route for heavy jobs via worker routing (Pass 0.094/0.095). |

## Health

- Liveness: `GET /health/live`
- Readiness: `GET /health/ready` (AMP operational validation default)

## Pass boundaries

| Pass | Scope |
| --- | --- |
| **0.093** | AMP template foundation, storage mapping, backup/restore safety, worker routing contract, Cloudflare team-domain normalization |
| **0.094** | Public AMP runtime image + private release bundle (pre-cutover template) |
| **0.095** | Publish runtime image and private GitHub Release bundle (no template cutover yet) |
| **0.098** | Cut over AMP template to public runtime + pinned immutable private release tag and SHA-256 |

## Related documentation

- `installation-checklist.md`
- `migration-checklist.md`
- `backup-restore-checklist.md`
- `update-rollback-checklist.md`
- `storage-mapping.md`
- `../../docs/PASS_0_094_AMP_PUBLIC_RUNTIME_PRIVATE_RELEASE.md`
