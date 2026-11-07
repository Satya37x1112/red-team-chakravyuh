# VAJRAPRAHAAR — Project Status / Update

**As of:** 2026-11-07 · AI Red Team Cyber Range Console (academic project)

Point-wise summary of everything built and decided so far. Nothing here runs
against any system — it is a status record.

> **Scope reminder:** This is a defensive/educational console for an **isolated,
> authorized lab network** only. Never point it at internet-facing or
> shared-hosted systems.

---

## 1. What the project is
- An AI agent reads **real telemetry** from an isolated, authorized lab target,
  reasons over it with an LLM, and a dashboard shows three layers:
  **REAL LAB TELEMETRY → AGENT DECISION (AI) → ANALYSIS (AI)**.
- **Backend:** FastAPI — telemetry collector, DB, WebSocket, AI decision engine
  (via OpenRouter), attack modules.
- **Frontend:** React + TypeScript + Tailwind dashboard (Vite).
- **Three attack modules:** DDoS, Brute-force, RAT.
- **Safety-first:** fail-closed gating, hard caps, honest degradation, kill switch,
  cracked secrets never shown.

---

## 2. The 5 integrated tools (behind one adapter interface)
1. **CALDERA analyzer** — MITRE Caldera report → ATT&CK coverage + stats.
2. **Locust** — the real DDoS load driver (fail-closed, hard-capped).
3. **vervet** — signed adversary-emulation CLI (read-only scan).
4. **PentestGPT** — LLM pentest agent.
5. **THC-Hydra** — the real credential-test (brute-force) driver (added this cycle).

Each degrades honestly: missing tool/key/config → "unavailable" with a reason,
never a crash.

---

## 3. Work completed (point-wise)

### Documentation
- `WINDOWS_VM_SETUP.md` — install the console on a Windows VM (Docker / hybrid /
  bare-metal) + troubleshooting + security notes.
- `RUN_SERVERS.md` — start backend + frontend locally; **now also documents the
  two demo targets** (DDoS site :3000, brute-force SSH :5000).
- `WORKLOG_2026-11-04.md` — detailed worklog, with the 5-integrations table.
- `KALI.md` — complete step-by-step guide to run the whole thing on **Kali** and
  attack an authorized target **by IP** (all 3 attacks + a paste-ready AI prompt).
- `PROJECT_STATUS.md` — this file.

### THC-Hydra brute-force integration (new)
- New fail-closed `HydraIntegration` adapter + gated API endpoint
  (`POST /api/integrations/hydra/run`), registry entry, config settings.
- **Windows support:** real hydra installed in WSL + a Windows→WSL shim
  (`backend/tools/hydra.cmd` + `hydra-wrap.sh`) since hydra has no native Windows
  binary. On Kali this isn't needed — `HYDRA_BIN=hydra` is native.
- **`HYDRA_PORT`** support added (attack a service on a non-default port).
- **Attack visualization** on the dashboard: "CREDENTIAL CRACKED" banner,
  attempts made/total, "cracked at #N", duration, progress bar, and a live attempt
  feed with every guessed **password masked** (secret never revealed).

### Brute-force AI wordlist (improved)
- Suggested wordlist is now **telemetry-targeted** — permutes the observed
  hostname/account with the current year, seasons, and common patterns.
- **Confirmed-weak feedback:** a credential a real authorized lab run cracked
  (e.g. the demo's planted one) is added and **ranked first**; highlighted in the
  WordlistPanel.

### DDoS path (fixed + demo)
- Root cause fixed: the stock locustfile throttled to ~8 requests; a new zero-wait
  load profile (`vajra_load.py`) now generates **real load (~380 req/s)**.
- Run summary sums per-endpoint rows → Requests / Req-s / Failures tiles.
- `backend/tools/demo_site.py` — a fragile single-threaded demo site; verified it
  goes **unavailable under the DDoS load**, then recovers (all on localhost).

### Brute-force demo target
- `backend/tools/demo_ssh_target.sh` — a deliberately-weak SSH target (one
  throwaway `labadmin` account) inside WSL; Hydra **successfully cracked** it
  end-to-end, proving the pipeline + visualization.

### Bug fixes
- Frontend wouldn't build on Windows: `report.ts` vs `Report.tsx` case collision →
  renamed to `reportHtml.ts`.
- Fixed a corrupted hydra wrapper (shell vars stripped at creation); added
  `.gitattributes` to keep `.sh` files LF.

---

## 4. Decisions & boundaries (important)
- **Refused to point the DDoS tool at an external hosted URL** (`*.ai.studio`).
  Reason: it is internet-facing shared infrastructure; owning the app doesn't
  authorize flooding the platform. Load/DoS stays on isolated localhost / an
  authorized lab target only.
- **RAT by IP alone is not possible** (an implant needs initial access). The
  honest, legitimate **3rd attack = credentialed remote access / post-exploitation**:
  use creds from the brute-force step with `netexec` / `evil-winrm` / `impacket`
  to run commands on the Windows target over SMB/WinRM — no implant uploaded.
- **AI-driven** means: the LLM agent reads real telemetry/results and produces the
  per-module **decisions + analysis** (never fabricated; honest `llm_unavailable`
  without an OpenRouter key). The tools (hydra/locust/nxc) do the execution.

---

## 5. How a target is attacked by IP (Windows VM)
| Attack | Lands on | Needs |
|--------|----------|-------|
| **DDoS** (Locust) | web service (80/443/8080) | HTTP service open |
| **Brute-force** (Hydra) | login service (RDP 3389 / SMB 445 / SSH 22) | auth port open |
| **Remote Access** (netexec/evil-winrm) | SMB/WinRM with valid creds | creds from brute-force + 445/5985 open |

Always **recon first** (`nmap -sV <IP>`) — open services decide what's possible;
a locked-down target means nothing lands (honest reality).

---

## 6. Current state
- All code + docs are **committed** and pushed (Hydra integration, visualization,
  wordlist, demo targets, HYDRA_PORT, Kali guide).
- No services are left running (demos were stopped).
- OpenRouter API key must be set in `.env` for the AI-driven decisions to be live.

---

## 7. Next steps (to complete the project)
1. **Migrate to Kali** (recommended) — native hydra/nmap/netexec; follow `KALI.md`.
2. Get the authorized **target VM's IP**; run `nmap` to map open services.
3. Wire `.env` to the target IP; run the three attacks (DDoS → Brute-force →
   Remote Access) as the kill-chain demo.
4. (Optional) Build a **"Remote Access" integration adapter** (wraps `netexec`) so
   the 3rd attack runs from the dashboard too — see the paste-ready prompt in
   `KALI.md` §14.
5. Set `OPENROUTER_API_KEY` so decisions/analysis are AI-driven.
6. Capture screenshots / recording for the PPT (prompt for the deck already
   provided).

---

See also: `KALI.md`, `RUN_SERVERS.md`, `WINDOWS_VM_SETUP.md`, `WORKLOG_2026-11-04.md`.
