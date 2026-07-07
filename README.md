# PolyToPixel on AMP (Pass 0.093)

PolyToPixel runs on CubeCoders AMP Generic Module using the private GHCR pilot image. AMP is the always-on control plane and persistent project host on Ubuntu 24.04 x86_64.

## Architecture

- **AMP instance** runs `ghcr.io/warguy500/polytopixel:<image-tag>` with localhost binding on port **21617**.
- **Bundled cloudflared connector** (enabled by default) publishes `app.polytopixel.ai` to `http://127.0.0.1:21617` inside the container.
- **Cloudflare Access** protects the public hostname. Production identity example: `polytopixel.admin@gmail.com`.
- **Shared workspace** label in the UI: `Cart Horse Studios Shared`.
- **Persistent state** survives image replacement through AMP instance datastore bind mounts.

## Template files

| File | Purpose |
| --- | --- |
| `polytopixel.kvp` | AMP Generic Module application definition |
| `polytopixelconfig.json` | AMP settings manifest |
| `polytopixelmetaconfig.json` | Maps AMP settings to `polytopixel.env` |
| `polytopixel.env` | Default instance environment template |
| `env.example` | Documented production environment variables |

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
| **0.094** | Timothy's Windows RTX 4070 Ti local worker installation and heartbeat |
| **0.095** | RunPod fallback orchestration and remote execution |

## Related documentation

- `installation-checklist.md`
- `migration-checklist.md`
- `backup-restore-checklist.md`
- `update-rollback-checklist.md`
- `storage-mapping.md`
- `../../docs/PASS_0_093_AMP_DEPLOYMENT_FOUNDATION.md`
