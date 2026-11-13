# AI RED TEAM — Environment Variables (`backend/.env`)

Secrets live only in the gitignored `backend/.env` (never committed).

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEY` (+ `_DDOS/_BRUTEFORCE/_RATUBA`) | LLM credentials (spread per module) |
| `OPENROUTER_MODEL` / `OPENROUTER_FALLBACK_MODELS` | model + fallbacks |
| `TELEMETRY_SOURCE` | `local` / `blackbox` / `winrm` / `none` |
| `SAFETY_TARGET_ALLOWLIST` | targets authorized for all gated modules |
| `SAFETY_ADMIN_TOKEN` | kill-switch reset token |
| `DISCOVERY_*` | discovery enable/subnets/prohibited/concurrency |
| `HYDRA_*` / `LOCUST_*` / `REMOTE_ACCESS_*` | per-adapter config + caps |
