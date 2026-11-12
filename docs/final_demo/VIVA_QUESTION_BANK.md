# CYBER CHAKRAVYUH — Viva Question Bank (65 Q&A)

## 1. Project fundamentals
1. **What is CYBER CHAKRAVYUH?** An AI-assisted Red-vs-Blue lab platform on Kali: dashboard + FastAPI backend where an LLM proposes bounded assessments and deterministic Python authorizes/executes/audits them.
2. **Why "AI-assisted" not "AI-autonomous"?** The AI only produces structured plans; it has no handle to run tools. Execution and authorization are deterministic and AI-independent.
3. **Stack?** FastAPI + Pydantic (backend), React/TS/Vite (frontend), Tailscale (connectivity), Hydra/Locust/NetExec (tools), SQLite (audit), OpenRouter/OmniRoute (LLM).
4. **What runs today vs blocked?** Live: discovery, authorization, recon, kill-switch, audit, 249 tests. Blocked: live Windows ops (target offline), AI inference (OpenRouter auth).
5. **Why Kali-only?** The attacker tooling + platform live on Kali; the Windows target is externally managed and never modified.

## 2. Cybersecurity concepts
6. **Reconnaissance?** Non-destructive information gathering (here: bounded TCP-connect probe of approved ports).
7. **Red vs Blue team?** Red = offensive assessment; Blue = defensive detection/response (SOC/Wazuh).
8. **Why "discovered ≠ authorized"?** Reachability is not permission; a host must pass central authorization before any assessment.
9. **Fail-closed meaning?** On any error/ambiguity the system denies, not allows.
10. **Why bounded operations?** To keep lab testing safe, repeatable, non-destructive, and legally scoped.

## 3. Red Team / Blue Team
11. **What Red-Team activity is generated?** Connection probes, (optional) bounded auth-failure signatures, capped load, read-only remote queries.
12. **How does Blue Team see it?** Only if the target has a SOC agent (Wazuh) + rules; CHAKRAVYUH has no event forwarding — detection is external.
13. **Example detectable event?** Windows 4625 (failed logon) from a bruteforce signature → a Wazuh logon-failure rule.
14. **Is Blue-Team detection proven?** Not in-code; requires an online target + agent + rule chain (documented in RED_TEAM_BLUE_TEAM_FLOW).
15. **UBA role?** `app/modules/uba.py` scores behavior over available telemetry (defensive analytics).

## 4. AI & LLM integration
16. **Which model/provider?** `anthropic/claude-sonnet-4.5` via OpenRouter; optional OmniRoute gateway.
17. **One centralized client?** Yes — `app/integrations/_llm.py`; no per-module LLM clients.
18. **What does the planner output?** A Pydantic `ExecutionPlan` (module, target, requested params) — never caps or an approval flag.
19. **If the LLM is down?** `(None, None, errors)` → deterministic fallback plan labeled FALLBACK (NOT AI); no fabrication.
20. **Does AI see secrets?** No — credentials never enter prompts/logs/audit; the client sanitizes errors.

## 5. Backend architecture
21. **Request lifecycle?** Dashboard→FastAPI→(planner)→ExecutionPlan→Gateway→Registry→Dispatcher→Adapter→Telemetry→Audit→Dashboard.
22. **Where is the single source of truth for authorization?** `gateway.evaluate()` + `policy.py` (+ `authorize_recon_target` for recon routes).
23. **How are results streamed?** WebSocket `/ws` via `useLive.ts`, plus REST.
24. **Execution registry purpose?** Track each execution (id, state, cancellation) — `app/safety/registry.py`.
25. **Is the registry persistent?** No — in-memory per process; audit is persisted in SQLite.

## 6. Safety Gateway & authorization
26. **Gateway checks, in order?** kill-switch → module enabled → adapter available → target allowlist → operation allowlist → clamp caps → concurrency → create record.
27. **Can a plan raise a cap?** No — caps live in `policy.py`/config; the schema has no cap field; params are clamped *down* only.
28. **Rejected plan reaching an adapter?** Impossible — no APPROVED registry record is created, and the dispatcher only runs APPROVED records.
29. **Operation allowlist?** For NetExec, only 5 fixed identifiers are permitted; anything else is rejected (no command strings).
30. **Concurrency safety?** Atomic check+reserve under one lock (TOCTOU-fixed), plus `safety_max_concurrent_executions`.

## 7. Network Discovery
31. **How are peers found?** `tailscale status --json` parsed in `discovery.py` (not a scan).
32. **Peer initial state?** `pending` — never auto-authorized.
33. **How to authorize?** Explicit `POST /api/network/targets/select` → `authorize_recon_target()`.
34. **Lab-subnet sweep default?** Disabled; requires explicit enable + non-empty allowlist (empty denies).
35. **Does rediscovery change authorization?** No — authorized state preserved; a selected target stays selected only while authorized.

## 8. Hydra / authentication testing
36. **Purpose?** Bounded credential-resilience testing of an authorized service.
37. **Integration?** `/api/integrations/hydra/run` → Gateway → Registry → Dispatcher → `HydraIntegration`.
38. **Attempt limits?** `hydra_max_attempts` cap; `live-validate` ≤3/account, non-admin only.
39. **Lockout safety?** Lockout-aware design + bogus-username signatures to avoid locking real accounts.
40. **Live vs mock here?** MOCK VERIFIED only; no live auth attempts performed.

## 9. Locust / availability
41. **Purpose?** Bounded HTTP load/resilience testing — not DDoS.
42. **Caps?** ≤50 users, ≤120 s, Gateway-clamped.
43. **Simulation mode?** `locust_sim.py` — synthetic metrics, labeled "SIMULATION — NO NETWORK TRAFFIC", no traffic.
44. **Sim vs real separation?** Different adapters (`locust` vs `locust_sim`); sim can never invoke the real adapter.
45. **Cleanup/cancel?** Headless subprocess, kill-switch + process-group termination.

## 10. NetExec / remote administration
46. **Purpose?** Authenticated **read-only** remote info — no shell.
47. **Five operations?** connectivity_check, whoami, hostname, os_info, system_info.
48. **Arbitrary commands?** Not supported — only fixed operation identifiers map to fixed implementations.
49. **Credential handling?** Protected config/stdin; never in argv/logs/audit (one documented brief-argv caveat).
50. **Status?** IMPLEMENTED — NOT LIVE VERIFIED (target offline).

## 11. Telemetry & UBA
51. **Telemetry sources?** Agentless blackbox TCP probe, WebSocket events, SQLite audit.
52. **Measured values?** Reachability, open ports, latency, request/latency metrics (Locust).
53. **Unavailable values?** Windows CPU/RAM/event-log — external probe can't see inside; reported unavailable.
54. **Fabrication policy?** None — missing data is "unavailable"; offline target = "unreachable".
55. **UBA scoring?** Statistical behavior scoring over available telemetry.

## 12. Wazuh / SIEM
56. **Is Wazuh integrated in code?** No — no forwarding/connector code exists; Blue-Team runs on the target's own stack.
57. **How would an op reach Wazuh?** Online target + Wazuh agent + audit policy + matching rule.
58. **What does CHAKRAVYUH persist?** Its own SQLite audit (local) — not a SIEM feed.
59. **Honest claim?** "We generate detectable activity; detection is external and unproven in-code."

## 13. File transfer & integrity
60. **Flow?** Operator starts visible Windows receiver → authenticated transfer → SHA-256 before/after → integrity verified → audit.
61. **Safety?** Filename/path-traversal sanitization, 10 MB cap, no execution of received files.
62. **Status?** IMPLEMENTED — NOT VERIFIED (receiver not started).

## 14. Testing, deployment, limitations
63. **Test count/command?** 249 passing; `PYTHONPATH="$PWD:$PWD/.venv/lib/python3.13/site-packages" /usr/bin/python3.13 -m pytest -q`.
64. **Why the python3.13 invocation?** venv interpreter is 3.14 but packages are under python3.13 (documented env mismatch).
65. **Biggest honest limitations?** Windows offline, OpenRouter auth, non-unified routes, no Wazuh code, in-memory registry. All in LIMITATIONS_AND_FUTURE_SCOPE.
