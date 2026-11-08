# CYBER CHAKRAVYUH — Phase 0: Complete Repository & Platform Audit

**Author:** Implementation engineer (Claude Code, on Kali) — auditor
**Date:** 2026-11-08
**Nature:** READ-ONLY audit for the new master scope (OmniRoute, network isolation, controlled proxy framework, Nmap discovery, operator-dashboard expansion). No source changed, no commits, no target contact, no installs, no live calls. All existing work preserved.

Statuses: `IMPLEMENTED` · `MOCK VERIFIED` · `LIVE VERIFIED` · `BLOCKED` · `NOT VERIFIED` · `NOT IMPLEMENTED` · `UNSUPPORTED` · `REQUIRES OWNER DECISION`.

---

## 1. Existing architecture (what is already built and verified)

The platform from Sections 1–4 + Stages 5.1–5.4 is intact and **mock/code-verified** (141 tests; 140 pass offline + 1 live-LLM deselected; frontend typecheck+build clean). Pipeline:

`Objective → Context (agent/context.py) → Centralized Planner (agent/planner.py) → ExecutionPlan (safety/plan_schema.py) → Safety Gateway (safety/gateway.py) → Registry (safety/registry.py) → Dispatcher (safety/dispatcher.py) → Adapter (integrations/*) → Analysis (agent/analysis.py) → Feedback (agent/feedback.py) → Audit/DB (models.py) → Dashboard`.

- One centralized LLM client: `agent/llm.py::default_llm` → `integrations/_llm.py::complete` (OpenRouter, OpenAI-compatible, honest fallback). **This is the single integration point for OmniRoute.**
- Three modules: Hydra (auth testing), Locust (bounded load), NetExec (credentialed remote admin, 5 read-only ops — **not a RAT**). Blackbox telemetry (IP-only, authorized + bounded). WinRM telemetry (implemented, live-unverified).
- Safety Gateway + unified kill switch + execution registry + secret-masked audit — all `IMPLEMENTED AND MOCK VERIFIED`.

## 2. Completed functionality inventory (keep — do not rebuild)

| Area | Status |
|---|---|
| Centralized AI planner + feedback loop | IMPLEMENTED, MOCK VERIFIED |
| Hydra / Locust / NetExec adapters | IMPLEMENTED, MOCK VERIFIED; LIVE UNVERIFIED |
| Blackbox telemetry (auth + bounded) | IMPLEMENTED, MOCK VERIFIED |
| WinRM / local / none telemetry | IMPLEMENTED; WinRM LIVE UNVERIFIED |
| Safety Gateway + target/operation allowlists | IMPLEMENTED, MOCK VERIFIED |
| Execution registry + unified kill switch | IMPLEMENTED, MOCK VERIFIED |
| Audit logging (secret-masked) + SQLite | IMPLEMENTED, MOCK VERIFIED |
| Frontend (AI Planner, Remote Access, Target Recon, Integrations, Operations, Dashboard, History, Reports) | IMPLEMENTED; VERIFIED BY CODE (typecheck+build) |
| 141-test suite | IMPLEMENTED, MOCK VERIFIED |

## 3. Missing functionality inventory (new master scope — NOT yet built)

| New requirement | Status | Evidence |
|---|---|---|
| **OmniRoute self-hosting** (AI gateway) | NOT IMPLEMENTED · REQUIRES OWNER DECISION | no `omniroute`/`LLM_BASE_URL` code; not installed |
| **Generic LLM provider config** (`LLM_PROVIDER/BASE_URL/API_KEY/MODEL`) | NOT IMPLEMENTED | client hardcodes OpenRouter settings (easy to generalize) |
| **Nmap discovery adapter** | NOT IMPLEMENTED | no nmap code in `backend/app` (nmap binary present at `/usr/bin/nmap`); `vervet` does a limited T1046 connect-scan only |
| **Network Gateway Manager / Verifier / Health Monitor** | NOT IMPLEMENTED | no networking code |
| **IP Telemetry Manager (source-IP attribution)** | NOT IMPLEMENTED | — |
| **Fail-Closed network Controller** | NOT IMPLEMENTED | — |
| **Controlled Proxy Framework** | NOT IMPLEMENTED · REQUIRES OWNER DECISION | no proxy code; requirements ambiguous (prompt acknowledges this) |
| **Frontend: Network Management, Proxy & Gateway, Audit Logs, Settings, full Target Discovery** | NOT IMPLEMENTED | current routes lack these |
| New backend APIs (interfaces, gateway, verification, proxy, nmap, source-IP, provider/OmniRoute health) | NOT IMPLEMENTED | — |

## 4. Frontend ↔ backend integration map (current)

Frontend (`frontend/src/api.ts`, relative `/api`, Vite proxy → `:8077`) → real backend routes. Current pages/routes: `/` Dashboard, `/central` Operations Center, `/planner` AI Planner, `/remote-access`, `/recon` Target Recon, `/integrations`, `/ddos` `/bruteforce` `/rat` (Operation), `/history`, `/report` `/reports`, `/agent`, `/range`. WebSocket `/ws` for live events.

Required-vs-present (the 11 target sections): Overview ✅ · AI Planner ✅ · Integrations ✅ · Target Discovery ⚠️ (Target Recon = blackbox telemetry only, no nmap) · Active Operations ⚠️ (via Operations Center/History) · Telemetry ⚠️ (via Target Recon/panels) · Attack Modules ⚠️ (via Integrations + per-kind pages) · **Network Management ❌** · **Proxy & Gateway ❌** · **Audit Logs ❌ (no dedicated page)** · **Settings ❌**.

## 5. Network architecture assessment — ⚠️ BLOCKER / REQUIRES OWNER DECISION

**Described deployment:** attacker = separate physical laptop; Kali in VMware; target = separate Windows laptop; both laptops on the **same mobile hotspot**.

**Observed reality (this VM):** Kali `eth0 = 192.168.176.131/24`, default gateway `192.168.176.2`. The `.../24` with a `.2` gateway is a **VMware NAT network**, **not** a bridged hotspot LAN. Consequences:
- Under VMware **NAT**, the Kali VM is **behind the host** and is **not an L2 peer** of a Windows laptop on the hotspot — the target is likely **not directly reachable**, and "source-IP attribution" would show the **host/NAT** address, not Kali.
- For the described lab to work, VMware must be in **bridged** mode (Kali joins the hotspot subnet directly) **or** a routed/host-only lab must be defined. The prompt itself says: *do not assume bridged mode is available or correct.*
- **No live lab traffic (Hydra/Locust/NetExec/nmap) can be verified until the actual network path to the target is established and confirmed.**

This is the single biggest blocker and needs an explicit owner decision before any network/proxy work.

## 6. Proxy compatibility assessment — honest, per module

The new "controlled proxy framework" assumes lab traffic can be routed through an approved proxy/gateway. **Transport reality (do not over-claim):**

| Module | Transport | Native proxy support | Assessment |
|---|---|---|---|
| **Nmap** | raw packets / connect | **No** native SOCKS/HTTP proxy for SYN/host-discovery (connect-scan can go via proxychains for TCP connect only) | PARTIALLY UNSUPPORTED |
| **Hydra** | protocol sockets (ssh/rdp/smb/…) | **No** built-in proxy | UNSUPPORTED via ordinary proxy (would need proxychains, unreliable per-protocol) |
| **Locust** | HTTP(S) | **Yes** (HTTP(S)_PROXY / configured client) | SUPPORTED (HTTP proxy) |
| **NetExec** | SMB/WinRM over TCP | Partial (some impacket paths support SOCKS via proxychains) | PARTIALLY SUPPORTED |
| **Blackbox** | TCP connect | connect() can be wrapped (proxychains) but it is a probe, not a tunnel | PARTIALLY SUPPORTED |

**Conclusion:** a blanket "all modules routed through one proxy chain" is **not truthfully achievable**. The framework can honestly manage/verify a proxy for the modules that support it (Locust, and connect-based paths via an authorized gateway) and must **report the others as UNSUPPORTED** rather than claim routing. This matches the prompt's own rule: *do not falsely claim a module is routed through the proxy.*

> **Ethical guardrail (reaffirmed, per the prompt):** this subsystem is for **route verification, source-IP attribution evidence, and fail-closed enforcement on authorized lab infrastructure only** — **not** anonymity, evasion, concealment from monitoring, open-proxy/residential-proxy harvesting, or rate-limit/block bypass. Any of those are out of scope and will not be implemented.

## 7. OmniRoute assessment (from the official repo)

- **What it is:** an MIT, **OpenAI-compatible AI gateway** (`/v1/chat/completions`, `/v1/responses`) aggregating ~380 providers with quota-aware fallback. Example endpoint `http://localhost:20128/v1`.
- **Runtime/install:** TypeScript/Node.js (Next.js); `npm` package `omniroute` (also Docker/Electron). Runs `omniroute serve --headless`. **Installable natively on Kali via npm/pnpm (user-level, no Docker, no sudo).**
- **Free inference?** **No** — "bring your own provider accounts"; it aggregates providers' free tiers / your keys (it is *not* a token grant). Some keyless/free-tier providers exist but may be unreliable.
- **Auth:** `Authorization: Bearer <OMNIROUTE_KEY>`.
- **Integration effort:** **LOW** — the existing `_llm.complete` already uses the OpenAI SDK with a configurable `base_url` + `api_key`. Pointing it at OmniRoute = add `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL` settings that **default to the current OpenRouter values** (preserving OpenRouter). No per-module AI clients — the planner stays centralized.
- **Benefit for this project:** OmniRoute's free-tier routing could help with the current "paid model BLOCKED (OpenRouter credits)" limitation — but only if a usable free provider is configured; not guaranteed.

## 8. Proposed implementation sequence (incremental; each gated on owner approval)

1. **(Blocker first) Network reality decision** — owner confirms the real lab network (VMware bridged vs host-only vs routed) and the actual target IP/reachability. *No network/proxy code until this is settled.*
2. **Generic LLM provider config** (small, low-risk): add `LLM_PROVIDER/LLM_BASE_URL/LLM_API_KEY/LLM_MODEL` to the central client, defaulting to OpenRouter (preserves everything). Enables pointing at OmniRoute **or** any OpenAI-compatible gateway without installing anything.
3. **(Optional) OmniRoute self-hosting** (npm, user-level, loopback) + a provider-status/health API + an "AI Gateway" status card. Only if the owner wants to self-host.
4. **Nmap discovery adapter** (bounded, authorized-scope, does not auto-authorize targets) + discovery API + Target Discovery page.
5. **Network subsystem** (interfaces/routes read-only; Gateway Manager; Network Verifier; IP Telemetry; Fail-Closed Controller) + APIs + Network Management page.
6. **Controlled proxy framework** (only for supported modules; honest UNSUPPORTED labels) + Proxy & Gateway page — **only after the owner specifies the actual authorized lab proxy/gateway**.
7. **Frontend expansion** (Audit Logs, Settings, polish) + API wiring.
8. **Testing + docs + final security review** at each step (mock vs live clearly separated).

## 9. Owner decisions required (before implementation)

1. **Network topology (BLOCKER):** What is the real intended lab network? Is VMware to be set to **bridged** (so Kali is a hotspot peer)? What is the authorized target's actual IP, and is it reachable from Kali today? *(Nothing live works without this.)*
2. **Proxy-chain requirements (ambiguous):** Is there a concrete, **authorized** lab proxy/gateway (e.g., a SOCKS proxy on the attacker laptop, a lab jump host)? If so, its address/protocol. If not, the proxy framework can only be a **route-verification + fail-closed** layer, not an actual traffic tunnel. Confirm scope = authorized infrastructure, no evasion.
3. **OmniRoute:** Do you want us to **install and self-host OmniRoute** (npm, user-level), or only **generalize the LLM config** so you can point at OmniRoute/any OpenAI-compatible gateway yourself? (Recommended: start with the config generalization — lower risk.)
4. **Nmap module:** Approve building a **bounded nmap discovery adapter** (authorized scope, no auto-authorization), or keep recon manual via the CLI?
5. **Scope realism:** acknowledge that Hydra/Nmap are **UNSUPPORTED** for ordinary proxy routing, so "every module through the proxy" will be reported honestly, not forced.

## 10. Phase 0 conclusion
The existing platform is solid and preserved. The new master scope is **largely greenfield** (OmniRoute, network isolation, proxy framework, nmap, several dashboard pages) and contains **one hard blocker (network topology)** and **two genuinely ambiguous areas (proxy-chain, OmniRoute scope)** that need owner decisions. **No implementation performed.** Recommend resolving the §9 decisions, then proceeding incrementally from §8 with per-phase approval.

Git: branch `main`; only prior-stage docs uncommitted (preserved). No source changed in Phase 0.
