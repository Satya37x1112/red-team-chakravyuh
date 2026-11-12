# CYBER CHAKRAVYUH — Limitations & Future Scope

## Current limitations (evidenced)
1. **Windows target offline** — `opensoc-windows`/`100.80.167.51` "offline, last seen 12h"; NetExec/file-transfer/live-connectivity **not live-verified**.
2. **OpenRouter auth failing** — AI inference **blocked**; deterministic fallback works. Owner must refresh the key in `backend/.env`.
3. **File-transfer receiver dependency** — requires operator to start the visible Windows receiver (`tools/windows_receiver.py`).
4. **Non-unified routes** — `/api/telemetry/probe`, `/api/attacks/soc-activity`, `/api/assessment/run`, `/api/auth/live-validate`, `/api/transfer/send` use central authz + kill-switch + audit but are **not** in the ExecutionPlan/Registry/Dispatcher pipeline.
5. **Windows internal telemetry unavailable** — an agentless external probe cannot read CPU/RAM/event-log; reported as unavailable.
6. **No in-code Wazuh/SIEM integration** — Blue-Team detection is external (target-side SOC).
7. **Python env mismatch** — venv interpreter is 3.14 but packages are under 3.13; tests use the explicit `python3.13` invocation.
8. **Vite** binds IPv4 `127.0.0.1` (fixed); `anyio` deprecation warning originates in starlette TestClient (not our code).

## Future scope (proposed — NOT implemented)
- Unify the legacy routes into ExecutionPlan/Registry (unique execution IDs + lifecycle + cancellation for all).
- Optional **Wazuh connector** to correlate CHAKRAVYUH operations with SOC alerts (with live evidence).
- Reliable live Windows telemetry via an authorized WinRM/agent path.
- Robust multi-provider AI fallback (OpenRouter ↔ OmniRoute ↔ local).
- Expanded observability (per-execution timeline, metrics) and test coverage.
- Reproducible environment (pinned venv for Python 3.14; one-command bring-up).
