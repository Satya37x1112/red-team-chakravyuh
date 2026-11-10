# CHAKRAVYUH — Stage 5 Network Validation

**Date:** 2026-11-10 · Read-only network/Tailscale validation. No network settings or source changed.

## A. Kali network baseline
- `eth0`: `10.238.79.204/24`, default via `10.238.79.112` (DHCP; changes between sessions — normal).
- `tailscale0`: `100.80.154.42/32`, UP. Loopback present. No exit-node / Funnel / subnet routes.

## B. Tailscale status
- Kali `100.80.154.42` (`manoharisatyasarthak@`) — matches historical.
- Target `100.80.167.51` `opensoc-windows` (`onlymahibhatt@` — **different account**).
- Other peers: cyberkabbali, fedora, soc-server. `netcheck`: UDP ok, DERP Mumbai, IPv4 reachable.

## C. Target identity & reachability
- **ONLINE** — `tailscale ping 100.80.167.51` → `pong from opensoc-windows` (~90–359 ms via tailnet).
- Identity confirmed (hostname opensoc-windows, tailnet peer). Route via `tailscale0` (table 52).
- **Reachable ≠ authorized**: owned by a different account; no active security testing without explicit owner authorization. Connectivity validated with non-disruptive `tailscale ping` only (no port sweep/scan).

## D. Route validation
- Target routes over `tailscale0` (not the default gateway). Public internet is a separate path.
- Distinctions available in backend telemetry: reachable / no-response / refused / filtered / partial (budget).

## E. Backend network-policy findings (fail-closed, verified by tests)
- `authorize_recon_target` (collector): IPv4 only; **RFC1918 or current tailnet peer** allowed; **public/global refused**; loopback refused.
- `/api/telemetry/probe` + `/api/attacks/soc-activity`: public IP → refused; kill-switch engaged → 423; both audited (RECON_PROBE / RECON_SOC_ACTIVITY).
- Gateway modules (hydra/locust/netexec): target allowlist + caps + kill-switch enforced in `evaluate()`.
- No broad network permission introduced. No silent policy bypass.

## F. Security findings
- No weakening of network restrictions. Tailscale membership not treated as authorization.
- No Windows/Tailscale-ACL/credential changes. No disruptive tests run.

## G. Files modified
- `docs/CHAKRAVYUH_STAGE_5_NETWORK_VALIDATION.md` (this file). **No source changes.**

## H. Test results
- Focused (blackbox/recon/gateway/killswitch): **44 passed**.
- Full backend suite: **171 passed**, 1 warning, 0 failed/skipped/deselected.
- Frontend typecheck: pass (0). Frontend build: pass (0).

## I. Remaining blockers
- Live module testing against `100.80.167.51`: **BLOCKED — AUTHORIZATION REQUIRED** (different-account owner; connectivity present, permission not documented).
- OpenRouter inference still auth-failing (unchanged; credential refresh is owner action).

## J. Verdict
**VERIFIED WITH LIMITATIONS** — Kali network + Tailscale validated, target online and reachable, backend network policy fail-closed and test-verified; the only limitation is that live testing remains authorization-gated (and AI inference credential-blocked).
