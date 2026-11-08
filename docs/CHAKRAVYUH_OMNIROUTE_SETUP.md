# CYBER CHAKRAVYUH — OmniRoute Self-Hosting Setup (Stage 2)

**Date:** 2026-11-08 · Status: **install BLOCKED on the current Node runtime.** Honest record of what was attempted, the exact blocker, and how to proceed. No secrets shown; no commit.

---

## 1. OmniRoute facts (from the official repo, github.com/cheaper-inference/OmniRoute)
- **What:** an MIT, OpenAI-compatible AI **gateway** (not an inference model; "bring your own provider keys") aggregating ~380 providers.
- **Install:** `npm install -g omniroute` (also `bun add -g`, `pnpm add -g omniroute@latest`, `npx -y omniroute`).
- **Node required:** `>=22.22.2 <23 || >=24.0.0 <27` (several transitive deps require `>=22.19`, `>=22.22`).
- **Run:** `omniroute` (serves gateway + dashboard) / `omniroute serve`. No documented `--headless` flag.
- **Default port:** `20128` (base URL `http://localhost:20128/v1`). Bind address not documented.
- **Config/data:** `~/.omniroute/` (config + SQLite DB).
- **Provider keys + gateway key:** via the **web Dashboard** ("Dashboard → Providers" to add a key; "Dashboard → Endpoints" to copy the gateway key). `omniroute tokens create` creates remote-mode tokens. **No documented env-var/CLI way to add a provider key headlessly.**
- **OpenAI-compatible endpoints:** `GET /v1/models`, chat completions under `/v1`.
- **Resources:** ~2 GB+ for dashboard + light chat; native builds (`better-sqlite3`, `@swc/core`).

## 2. Attempt + exact blocker (2026-11-08)
Environment: user-level Node at `~/.local/node` (`npm prefix` = `~/.local/node`, so `-g` installs are **user-level, no sudo**); build tools present (python3/make/g++/gcc); 54 GB free.

```
npm install -g omniroute   →  FAILED
  npm warn EBADENGINE  required: >=22.12.0 / >=22.19.0 / >= 22.22 ...  current: v22.11.0
  npm error code ERR_SSL_CIPHER_OPERATION_FAILED   (fatal — aborted the install)
```
- **Blocker 1 (runtime):** the installed **Node is v22.11.0**, below OmniRoute's required `>=22.22.2`. Multiple deps flagged `EBADENGINE`.
- **Blocker 2 (fatal):** `ERR_SSL_CIPHER_OPERATION_FAILED` (an OpenSSL GCM failure in this Node build) aborted the download/extract — **no binary was installed**.
- The partial module was removed; the tree is clean. **OmniRoute is NOT installed.**

## 3. Secondary blocker (even if install succeeds)
Provider configuration and the gateway key are **web-dashboard-driven** — there is no documented headless/env way to add a provider API key. Completing the provider setup therefore requires **opening the OmniRoute dashboard in a browser** (an interactive, owner-performed step), which cannot be done from the terminal alone.

## 4. How to proceed (owner decisions)
**To use OmniRoute:**
1. **Upgrade the user-level Node** to `>=22.22.2` (e.g. latest 22.x) or **24 LTS** — a user-level install to `~/.local/node` (no sudo). *Note: this replaces the current `~/.local/node` v22.11.0 that the frontend build uses; newer Node still builds Vite, but this is a deliberate environment change to flag.* (A newer Node also carries a newer OpenSSL, which should clear the cipher error.)
2. Re-run `npm install -g omniroute` (heavy; several minutes of native builds).
3. Start `omniroute`, confirm the actual port/bind, then **(owner, interactive)** open the dashboard, add a provider key, and copy the gateway key.
4. Wire into CHAKRAVYUH via Stage 1: `LLM_PROVIDER=omniroute`, `LLM_BASE_URL=http://127.0.0.1:<port>/v1`, `LLM_API_KEY=<gateway key>`, `LLM_MODEL=<model>`, then `POST /api/llm/test`.

**Or skip OmniRoute (live AI already works):** the Stage-1 generic client already reaches a live provider — **OpenRouter's free model works today** (default config). OmniRoute is a convenience gateway, not required for live AI.

## 5. Provider keys provided (status)
- **OpenRouter** (new key, in gitignored `.env`): paid model credit-limited; **free fallback model works → live AI available now**.
- **DeepSeek** (in gitignored `.env`): key is **valid and authenticates**, but the account returns **HTTP 402 Insufficient Balance** → no inference until balance is added. (Verified via a harmless probe through the Stage-1 generic client; no target contacted; key never logged.)

## 6. Security
`.env` is gitignored and untracked; both keys are stored only there and were never printed, logged, committed, or returned by any API. The Stage-1 client redacts keys from errors; the DeepSeek 402 error contained no secret.

## 7. Status
**OmniRoute self-hosting = BLOCKED** (Node `<22.22` + fatal SSL cipher error; plus dashboard-only provider config). **Integration readiness = config-ready** (Stage 1 supports `LLM_PROVIDER=omniroute`), but **NOT LIVE VERIFIED**. **Live AI overall = available** via OpenRouter's free model through the Stage-1 generic client.
