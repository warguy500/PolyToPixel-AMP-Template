# PolyToPixel on AMP (Pass 0.093–0.106)

PolyToPixel runs on CubeCoders AMP Generic Module. Pass 0.094 splits deployment into:

- **Public runtime image:** `ghcr.io/warguy500/polytopixel-runtime` (Blender, cloudflared, bootstrap — no app code)
- **Private release zip:** `polytopixel_release.zip` on GitHub Releases (application layer)

Pass 0.101 cuts the active template over to the AMP-compatible runtime and makes Generic Module bootstrap launch explicit.

Pass 0.102 fixes configuration category/subcategory metadata so all settings groups render without data-binding errors.

Pass 0.103 exposes the GitHub release token and Cloudflare tunnel token as visible masked password fields in the AMP settings UI.

Pass 0.104 launches bootstrap from the runtime-owned absolute path because AMP does not stage `control/` files into GenericApplication.

Pass 0.105 migrates application settings from incorrect `Application.*` keys to official Generic Module `App.*` namespace so AMP honors the launch contract.

Pass 0.106 corrects custom-setting env placeholder syntax and switches to direct runtime bootstrap executable launch per live AMP validation.

## Active runtime (Pass 0.101)

- **Image:** `ghcr.io/warguy500/polytopixel-runtime:runtime-git-328a94fca22e7e5384b1664b9732eedc0a8db9e4`
- **OCI index digest:** `sha256:e8764f06b1186622ee63910d6a0124d33781ff6f6be7c6817163350cf874ff09`
- **Application launch:** `/opt/polytopixel-bootstrap/amp_bootstrap_start.sh` (direct executable with Bash shebang)
- **Deploy root:** `POLYTOPIXEL_DEPLOY_ROOT={{$FullRootDir}}` in `App.EnvironmentVariables`
- **ConfigVersion:** `11` (runtime env expansion and live launch contract)

The superseded runtime tag `runtime-git-083c730cb290a55ef2158df1f8dc0a0acc8e0b00` must not be used for new instances.

## Secret entry (Pass 0.103)

Configure these through **visible masked password fields** in AMP (Release Download and Networking groups):

- **GitHub Release Token** — read-only access to private `polytopixel_release.zip` assets
- **Cloudflare Tunnel Token** — PolyToPixel tunnel connector

Never commit tokens, never log them, never include them in screenshots, and never place them in `App.CommandLineArgs` or other CLI argument fields. Values flow only through AMP masked password fields into `App.EnvironmentVariables`.

**AMP Event Log risk:** changing password fields may log values in plaintext (unresolved blocker). Do not enter replacement production tokens during namespace-only validation.

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

These files are synchronized to the public `PolyToPixel-AMP-Template` repository. They contain placeholders only.

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
| **0.100** | Correct runtime Dockerfile to preserve AMP `/ampstart.sh` contract |
| **0.101** | Cut over active template to corrected runtime + explicit Generic Module bootstrap launch; sync public template |
| **0.102** | Fix configuration category/subcategory data binding; ConfigVersion 7 |
| **0.103** | Expose secret fields as visible masked password inputs; ConfigVersion 8 |
| **0.104** | Launch bootstrap from runtime absolute path; ConfigVersion 9 |
| **0.105** | Migrate `Application.*` to `App.*` namespace; ConfigVersion 10 |
| **0.106** | Direct bootstrap executable, `{{FieldName}}` env placeholders, ForceIPBinding=False; ConfigVersion 11 |

## Related documentation

- `installation-checklist.md`
- `migration-checklist.md`
- `backup-restore-checklist.md`
- `update-rollback-checklist.md`
- `storage-mapping.md`
- `../../docs/PASS_0_102_AMP_CONFIG_CATEGORY_BINDING_FIX.md`
- `../../docs/PASS_0_103_AMP_SECRET_FIELDS_VISIBLE.md`
- `../../docs/PASS_0_104_AMP_BOOTSTRAP_LAUNCH_PATH.md`
- `../../docs/PASS_0_105_AMP_GENERIC_APP_NAMESPACE.md`
- `../../docs/PASS_0_106_AMP_RUNTIME_ENV_EXPANSION.md`
