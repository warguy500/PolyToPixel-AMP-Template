# PolyToPixel AMP installation checklist

- [ ] Ubuntu 24.04 x86_64 host with AMP Generic Module available
- [ ] 4 CPU cores and 8 GB RAM allocated (12 GB ceiling configured)
- [ ] RAID-backed storage with instance datastore on dedicated paths
- [ ] Import `deploy/amp/polytopixel/` template files into AMP (or future AMPTemplates repo)
- [ ] Create GHCR read-only token (`read:packages` least privilege) and store in AMP secrets
- [ ] Set `ImageTag` to verified digest tag `git-a1a4adc35077fac56f1f4fe08a20816195b49fed`
- [ ] Configure bind mounts per `storage-mapping.md`
- [ ] Set `ApplicationPort1=21617` and `SPRITESMITH_HOST=127.0.0.1`
- [ ] Set Cloudflare Access team domain and audience placeholders from Zero Trust
- [ ] Keep `BUNDLED_CLOUDFLARED_ENABLED=0` and `SPRITESMITH_CLOUDFLARE_TUNNEL_ENABLED=0`
- [ ] Configure external Cloudflare Tunnel route `app.polytopixel.ai -> http://127.0.0.1:21617`
- [ ] Do not expose container port 8000 publicly
- [ ] Start instance and verify `GET http://127.0.0.1:21617/health/ready`
- [ ] Sign in through Cloudflare Access as `polytopixel.admin@gmail.com`
- [ ] Confirm shared workspace label `Cart Horse Studios Shared` appears in session payload
