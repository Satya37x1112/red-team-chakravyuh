# CHAKRAVYUH — OmniRoute Manual Start / Stop Runbook (Kali)

**Audience:** the CHAKRAVYUH operator, for starting/stopping the local OmniRoute
AI gateway **by hand** on the Kali attacker machine.
**As of:** 2026-11-09 · OmniRoute **v3.8.53** · Node **v24.22.2** (user-level).

> OmniRoute is a local **gateway** (not an AI model). It forwards OpenAI-style
> `/v1` requests to a real provider (here: OpenRouter). It listens on
> **127.0.0.1:20128 only** (loopback) and requires an API key. No sudo. No Docker.

---

## 0. One-time facts (already set up)
- Gateway binary: `~/.local/node24/bin/omniroute` (runs on its own Node 24 at `~/.local/node24`).
- Config + database: `~/.omniroute/` (encrypted provider keys live here).
- Client key for `/v1`: stored at `~/omniroute-ops/gateway_client_key.secret` (mode 600).
- Logs: `~/omniroute-ops/omniroute.log`.
- A ready-made launcher: `~/.local/bin/chakravyuh-omniroute`.

---

## 1. START the gateway

### Easiest — foreground (press Ctrl+C to stop)
```bash
~/.local/bin/chakravyuh-omniroute
```

### Background (keeps running after you close the terminal)
```bash
setsid ~/.local/bin/chakravyuh-omniroute >/dev/null 2>&1 &
```

### Fully manual (equivalent, if you prefer typing it out)
```bash
export PATH="$HOME/.local/node24/bin:$PATH"
export DATA_DIR="$HOME/.omniroute"
OMNIROUTE_SERVER_HOST=127.0.0.1 PORT=20128 OMNIROUTE_HEADLESS=1 REQUIRE_API_KEY=true \
  omniroute serve
```
> ⚠️ **Always pass `REQUIRE_API_KEY=true`.** OmniRoute's shipped default is
> `false`, which would leave the inference endpoint open to any local process.
> The launcher already sets it to `true` for you.

Startup takes ~15–45 s. It is ready when the log shows **"OmniRoute is running!"**.

---

## 2. CHECK it is up (and secured)
```bash
# Is it listening on loopback only? (must show 127.0.0.1:20128, NOT 0.0.0.0)
ss -ltn | grep 20128

# Auth is enforced? (no key must return HTTP 401)
curl -s http://127.0.0.1:20128/v1/chat/completions -d '{}' \
  -H 'content-type: application/json' -w ' [HTTP %{http_code}]\n'
# expect: ... "Authentication required" ... [HTTP 401]
```

Harmless live test **through** the gateway (uses the stored client key):
```bash
export PATH="$HOME/.local/node24/bin:$PATH"; export DATA_DIR="$HOME/.omniroute"
KEY=$(cat ~/omniroute-ops/gateway_client_key.secret)
curl -s http://127.0.0.1:20128/v1/chat/completions \
  -H "Authorization: Bearer $KEY" -H 'content-type: application/json' \
  -d '{"model":"openrouter/auto","max_tokens":30,
       "messages":[{"role":"user","content":"Reply with CHAKRAVYUH OMNIROUTE CONNECTION SUCCESS."}]}'
```

---

## 3. STOP the gateway
```bash
export PATH="$HOME/.local/node24/bin:$PATH"; export DATA_DIR="$HOME/.omniroute"
omniroute stop
# If anything lingers:
pkill -f 'omniroute serve'
```

---

## 4. Make CHAKRAVYUH actually USE the gateway
By default CHAKRAVYUH talks to OpenRouter directly (works even if OmniRoute is
off). To route its AI **through** OmniRoute instead:

1. Start the gateway (section 1).
2. Edit `backend/.env` and **uncomment** these 4 lines (already present, pre-filled):
   ```
   LLM_PROVIDER=omniroute
   LLM_BASE_URL=http://127.0.0.1:20128/v1
   LLM_API_KEY=<the OmniRoute client key>
   LLM_MODEL=openrouter/auto
   ```
3. Restart the CHAKRAVYUH backend.
4. In the UI: **Settings → Test connection** should go green ("inference ok").

To go back to OpenRouter: re-comment those 4 lines and restart the backend.
> If the gateway is **not** running while those lines are active, CHAKRAVYUH's AI
> degrades honestly ("gateway unreachable") — it never invents output.

---

## 5. Common issues
| Symptom | Fix |
|---|---|
| `omniroute: command not found` | `export PATH="$HOME/.local/node24/bin:$PATH"` first. |
| `/v1` returns 401 with your key | Re-check the key in `~/omniroute-ops/gateway_client_key.secret`; mint a new one from the dashboard if needed. |
| Port 20128 busy | Something is already running — `omniroute stop` or `ss -ltnp | grep 20128`. |
| Listening on `0.0.0.0` | You started it without `OMNIROUTE_SERVER_HOST=127.0.0.1`. Stop and use the launcher. |
| Chat works without a key | You started it without `REQUIRE_API_KEY=true`. Stop and use the launcher. |
