# CYBER CHAKRAVYUH — OmniRoute Self-Hosting Setup (Stage 2)

**Date:** 2026-11-09 · Status: **INSTALLED, SECURED, LIVE-VERIFIED.** No secrets shown; nothing committed.

Supersedes the earlier "install BLOCKED on Node v22.11.0 + SSL cipher" record — that
blocker was resolved by installing a **separate** user-level Node 24 runtime (the old
Node 22 is preserved for the frontend).

---

## 1. OmniRoute facts (verified against the official repo + installed build)
- **What:** MIT, OpenAI-compatible AI **gateway** (not an inference model; bring-your-own provider keys).
- **Installed version:** **omniroute 3.8.53** (`npm view`/`omniroute --version`).
- **Node required (engines):** `>=22.22.2 <23 || >=24.0.0 <27`. We run it on **Node v24.22.2**.
- **Install (official, user-level, no sudo):** `npm install -g omniroute`.
- **Default port:** `20128`; API base `http://127.0.0.1:20128/v1`.
- **Bind host (verified env var):** `OMNIROUTE_SERVER_HOST` (default `0.0.0.0`) → set `127.0.0.1` for loopback-only.
- **Headless:** `OMNIROUTE_HEADLESS=1` (or `omniroute serve --headless`) — runs only the `/v1` proxy, dashboard disabled.
- **Auth (verified):** `REQUIRE_API_KEY` — **shipped default is `false`**; must set `=true` to gate `/v1/chat/completions`.
- **Config/data dir:** `~/.omniroute/` (`DATA_DIR`), incl. `storage.sqlite` (provider keys encrypted at rest via auto-generated `STORAGE_ENCRYPTION_KEY`).
- **OpenAI-compatible endpoints:** `GET /v1/models`, `POST /v1/chat/completions`, `/v1/responses`, …
- **Provider config (headless, verified):** `omniroute keys add <provider> --stdin` + `omniroute setup --non-interactive` + `omniroute providers test <id>` — **no browser required** (updates the earlier "dashboard-only" note).

## 2. Installation performed (2026-11-09)
1. Installed a dedicated user-level Node runtime (checksum-verified), leaving the existing Node 22 intact:
   - Downloaded `node-v24.22.2-linux-x64.tar.xz` from nodejs.org, **SHA256 verified** against `SHASUMS256.txt`.
   - Extracted to **`~/.local/node24`** (npm global prefix `~/.local/node24`, user-level, **no sudo**).
2. `npm install -g omniroute` → **omniroute@3.8.53** at `~/.local/node24/lib/node_modules/omniroute`, bin `~/.local/node24/bin/omniroute`.
   - Native deps resolved via prebuilt binaries (`better-sqlite3` `linux-x64.node`, `@swc/core`, `sharp`, `onnxruntime`, `keytar`). `npm ls -g omniroute` clean.
   - The earlier `ERR_SSL_CIPHER_OPERATION_FAILED` did not recur on Node 24 (newer OpenSSL).

**Existing Node 22 preserved:** `~/.local/node` (v22.11.0) is untouched and still used by the frontend build.

## 3. Secure runtime posture (Phase 3)
Started headless, loopback-only, auth-required:
```
OMNIROUTE_SERVER_HOST=127.0.0.1  PORT=20128  OMNIROUTE_HEADLESS=1  REQUIRE_API_KEY=true  DATA_DIR=~/.omniroute
```
Verified:
- **Loopback only:** `ss -ltn` shows `127.0.0.1:20128` (never `0.0.0.0`).
- **Auth enforced:** unauth/invalid key on `/v1/chat/completions` → **HTTP 401**; valid key → 200.
- **Headless:** dashboard disabled; only the `/v1` proxy is exposed.
- **Secrets:** provider key stored encrypted in `~/.omniroute/storage.sqlite` (added via `--stdin`, never in argv); client key in a `600` file; no key ever logged or printed.

> **Limitation found & handled:** `REQUIRE_API_KEY` ships `false` (inference plane open, loopback-protected only). We explicitly set it `true`. Also, `/v1/models` is always auth-gated independent of this flag.
> **Client-key provisioning:** the `/v1` client bearer key is normally minted in the dashboard (headless disables the UI). We minted one headlessly via OmniRoute's own authenticated local API (`POST /api/keys {name}`), keeping auth ON.

## 4. Provider configured (Phase 4)
- **Provider:** OpenRouter (`https://openrouter.ai/api/v1`), key added to OmniRoute via `omniroute keys add openrouter --stdin` (owner-supplied credential).
- **Model used for tests:** `openrouter/auto`.
- **Health:** `omniroute providers test openrouter` → `OK: provider test passed`.
- **Free tier / quotas:** OpenRouter routes to the account's available models; billing/limits are the owner's OpenRouter account's. OmniRoute itself adds no inference cost (it's a gateway).

## 5. Start / stop
See **docs/CHAKRAVYUH_OMNIROUTE_RUNBOOK.md** (manual start/stop) and the launcher `~/.local/bin/chakravyuh-omniroute`.

## 6. Known limitations
- `REQUIRE_API_KEY` default is `false` — must be forced `true` (launcher does this).
- `/v1` client-key minting is dashboard-oriented; we used the local authenticated API instead (documented).
- OmniRoute is a full Next.js app (~hundreds of deps); first install is heavy (several minutes of downloads).
- Live inference depends on the OpenRouter account having credit; OmniRoute does not provide free inference.
