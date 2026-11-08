# CHAKRAVYUH — Blackbox Telemetry Security Remediation

**Author:** Implementation engineer (Claude Code, on Kali)
**Date:** 2026-11-07
**Status:** Implemented and tested. 141/141 backend tests pass; frontend typecheck + build clean. No target contacted, no real port discovery (all socket ops mocked), blackbox telemetry not enabled, nothing committed.

Remediates the three findings from the Blackbox Telemetry security review: **MEDIUM-1** (target not allowlist-bound), **LOW-1** (no IP validation), **LOW-2** (unbounded sweep duration).

---

## 1. Files Changed

| File | Change |
|---|---|
| `backend/app/config.py` | +`blackbox_allowlist` (dedicated telemetry allowlist), +`blackbox_total_budget_seconds`, +`blackbox_allow_loopback` (test-only), +`blackbox_allowlist_set` property |
| `backend/app/telemetry/collector.py` | +`authorize_blackbox_target()` (IPv4 + RFC1918 + allowlist, no DNS); `BlackboxSource.collect()` authorizes **before any socket** and enforces a total **time budget** |
| `backend/app/telemetry/schema.py` | `NetworkProbe` +`complete`, +`ports_probed`, +`ports_total` (honest incompleteness) |
| `backend/app/.env.example` | documented blackbox address policy + allowlist + budget |
| `backend/tests/test_blackbox_telemetry.py` | rewritten — **all socket ops mocked** (no real port discovery); 23 tests |
| `frontend/src/types.ts` | `NetworkProbe` +`complete`/`ports_probed`/`ports_total` |
| `frontend/src/pages/TargetRecon.tsx` | honest "partial probe" banner when a sweep is cut short |

No attack module, Safety Gateway, or execution path was modified.

---

## 2. MEDIUM-1 — Authorized Target Validation

- A **dedicated** `BLACKBOX_ALLOWLIST` (comma-separated IPv4), kept **separate** from the attack-execution target policy (`SAFETY_TARGET_ALLOWLIST`) — no coupling between telemetry authorization and attack dispatch.
- `BlackboxSource.collect()` calls `authorize_blackbox_target(target)` **before opening any socket**; if the target is not authorized it returns honest **unavailable** telemetry and probes nothing (verified by `test_no_socket_opened_before_authorization`, which installs a socket tripwire).
- **Fail-closed:** an empty allowlist authorizes nothing. The target is config-only — the AI, API requests, and frontend controls cannot set or override it.

## 3. LOW-1 — Strict IP Validation (address policy)

`authorize_blackbox_target` uses the stdlib `ipaddress` module:
- **IPv4 literals only** — `ipaddress.IPv4Address(target)` rejects hostnames, IPv6, and malformed values. **No DNS resolution is ever performed.**
- **RFC1918 private only** — public/global IPs are rejected (`is_global`/`not is_private`).
- **Loopback** is rejected unless `BLACKBOX_ALLOW_LOOPBACK` is set — used **only by test fixtures**, never in production/`.env.example`.
- Must appear in `BLACKBOX_ALLOWLIST`.

Accepted address policy (documented in `.env.example`): *IPv4 literal + RFC1918 private + explicitly allowlisted.* Tests: authorized-private accepted; unauthorized-private, public, hostname, malformed, and loopback-without-flag all rejected.

## 4. LOW-2 — Probe Time Budget

- `BLACKBOX_TOTAL_BUDGET_SECONDS` (default 20s, clamped 0.05–300s) bounds the whole sweep. Before each port the elapsed time is checked; once the budget is exceeded the sweep stops.
- Individual socket timeouts stay clamped (0.2–10s); the port cap (64) is unchanged.
- **Honest incompleteness:** a budget-truncated sweep sets `complete=False` and records `ports_probed`/`ports_total`; **unprobed ports are simply absent — never invented as "closed"** (verified by `test_incomplete_probe_not_reported_as_closed`). The frontend shows a "partial probe" banner.
- No new dependency; simple sequential implementation with a wall-clock guard.

---

## 5. Test Results (exact)

```
cd backend && source .venv/bin/activate && python -m pytest tests/ -q
→ 141 passed, 1 warning in ~12s
```
`tests/test_blackbox_telemetry.py` = **23 tests, all with mocked sockets** (no real port discovery, no network): missing-config→unavailable; authorized-private accepted; unauthorized-private/public/hostname/malformed/loopback rejected; no-socket-before-auth; `authorize_blackbox_target` direct; budget enforcement; incomplete-not-closed; slow-port bounded; port-list cap; build_source selection; no-faked-inside-metrics; existing-telemetry compatibility; context scope labelling.

Frontend: `npm run typecheck` clean; `npm run build` ✓.

**No real target was contacted; no real port discovery was performed — every socket operation in the tests is mocked.**

---

## 6. Security Decisions & Remaining Limitations

- **Decision:** telemetry authorization is a **separate** dedicated allowlist, not the attack policy — deliberate decoupling per the review brief.
- **Decision:** default-deny on everything (empty allowlist, public IPs, hostnames, loopback) — fail-closed.
- **Residual (LOW):** the probe is still an active TCP connect-scan of the (now allowlisted, private) target; this is inherent to agentless telemetry and is bounded (≤64 ports, per-socket timeout, total budget). Authorized lab target only.
- **Residual (INFORMATIONAL):** `BLACKBOX_ALLOW_LOOPBACK` exists for tests; it is `False` by default and absent from `.env.example`, so production cannot probe loopback without an explicit, deliberate override.
- **Not changed:** blackbox remains **disabled by default** (`TELEMETRY_SOURCE=none`) and was **not enabled** during this work.

---

## 7. Git Status

Uncommitted (preserved; not committed per instructions): the blackbox feature files + this remediation across `config.py`, `collector.py`, `schema.py`, `.env.example`, `test_blackbox_telemetry.py`, `types.ts`, `TargetRecon.tsx`, plus the three docs. Branch `main`. Nothing pushed.
