# AI RED TEAM — Pre-Demo Checklist
- [ ] `./scripts/start.sh` → `./scripts/health.sh` both 200
- [ ] kill switch disengaged (`/api/health` → `halted:false`)
- [ ] LLM key valid (`POST /api/llm/test` → inference_ok)
- [ ] telemetry source = local (Kali metrics visible)
- [ ] (optional) Windows target online (`tailscale ping 100.80.167.51`)
- [ ] `make test` → green
