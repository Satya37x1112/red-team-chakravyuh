# CHAKRAVYUH — Section 4: Credentialed Remote Access / Post-Exploitation Demonstration (RAT Alternative)

**Author:** Implementation engineer (Claude Code, on Kali)
**Date:** 2026-11-07
**Status:** Implemented, tested, and hardened (3.1-style security remediation applied). 118/118 backend tests pass (37 for this module). Frontend typecheck + build clean. No NetExec was run against any target; no target contacted; no live authentication; no new dependency installed; nothing pushed.

> **Update (security remediation, same day):** the MEDIUM-1 argv credential exposure and LOW-1 exception-redaction findings from the Section-4 security review have been remediated — see §4 and §11. The password no longer appears on the `nxc` argv.

> Honesty up front: this module is **mock-verified** only. It is a genuine, integrated, safely-controlled capability — **not** a conventional RAT and **not** an unrestricted shell. Live NetExec/Evil-WinRM execution against a real target is **implemented but unverified**.

---

## 1. Architecture & Design Decisions

The third module reuses the entire Section-2/3 spine — it adds **no parallel safety mechanism**. The `rat_related` module identifier (reserved since Section 3) is now a real, gated capability:

```
Objective → Context (module now advertises approved operations) → AI Planner
   (selects module + OPERATION IDENTIFIER, never a command) → ExecutionPlan (schema)
   → Safety Gateway (adds an OPERATION-ALLOWLIST check) → Registry → Dispatcher
   → RemoteAccessIntegration (fixed argv per op id; NetExec read-only) → Analysis → Feedback
```

Design decisions:
- **Operation identifier, not a command.** The AI/API/user may only choose from a hardcoded allowlist of operation *ids*; the adapter maps each id to its **own fixed argv**. No command string from anywhere is ever executed. This is the core defence against it becoming a shell.
- **One safe underlying call.** All operations derive from a single read-only NetExec authentication + banner query (`nxc smb <target> -u <u> -p <p>`). No `-x`, no PowerShell, no `--exec`.
- **Reuse, don't duplicate.** Target allowlist, caps, concurrency, kill switch, registry, audit, dispatcher, planner, analysis and feedback are all the existing components, extended minimally for one new module.
- **Not a RAT.** No implant, persistence, stealth, keylogging, credential dumping, reverse shell, arbitrary upload/download, privilege escalation, or lateral movement. Nothing survives the session.

---

## 2. Adapter Implementation (`app/integrations/remote_access.py`)

`RemoteAccessIntegration` follows the Hydra/Locust adapter conventions (`status()` / `preconditions()` / `run()`, `_which`, managed `_run`). Fail-closed: `status()` reports unavailable without the NetExec binary, and not-runnable unless `REMOTE_ACCESS_ENABLED=true` **and** an authorized target **and** full lab credentials are configured.

`run(operation, run_seconds)`:
1. `preconditions()` gate (fail-closed) + reject any id not in `REMOTE_OPS`.
2. Build a **fixed argv** (`nxc <proto> <target> -u <user> -p <pass> [-d <domain>]`) — no shell, no command string.
3. Run via the managed-process runner (own process group, kill-switch reachable) with a hard timeout.
4. **Redact the password literal** from captured output *before* parsing (NetExec echoes it on the success line).
5. Project the redacted banner into the requested operation's fields.

---

## 3. Approved Operations (hardcoded allowlist, read-only)

| id | What it returns |
|---|---|
| `connectivity_check` | remote-management reachable + authenticated (true/false) |
| `whoami` | authenticated account identity, confirmed by successful auth |
| `hostname` | remote computer name (from the protocol banner) |
| `os_info` | remote OS string |
| `system_info` | hostname + OS + domain + SMB signing |

Unknown ids are rejected by the Safety Gateway (and again by the adapter). These are the **only** operations the module can perform.

---

## 4. Credential Handling

- Credentials come from local config (`REMOTE_ACCESS_USER` / `REMOTE_ACCESS_PASSWORD` in gitignored `.env`).
- **Never** in an ExecutionPlan, **never** sent to the LLM (the planner only sees module/target/operation), **never** in API responses, frontend state, audit logs, or exception messages.
- The password is **redacted** from captured NetExec output before anything is stored/returned (`_redact`), and `audit.mask_secrets` redacts credential-shaped keys. Verified by `test_password_never_in_result` and `test_audit_has_no_secret`.
- **Exception redaction (LOW-1):** any non-timeout exception from the subprocess is re-raised as a `RuntimeError` with the password redacted from its text (`test_exception_message_is_credential_redacted`).
- **No argv exposure (MEDIUM-1 remediated):** the password is **never** on the `nxc` command line. It is written to a short-lived file via `tempfile.mkstemp` (mode **0600**), preferring RAM-backed **`/dev/shm`**, and passed as `-p <file>` — NetExec reads a one-line file as a single-password list (verified against the installed NetExec 1.5.1 source, `connection.py:416`). The plaintext therefore never appears in `/proc/<pid>/cmdline`, `ps`, or the in-memory process registry. The file is **deleted on every path** (success / failure / timeout / cancellation) via `finally` + `_safe_unlink`. **Fail-closed:** if the secure file cannot be created, the run aborts — it never falls back to argv. Verified by `test_password_never_in_argv`, `test_credential_file_is_0600`, `test_credential_file_prefers_dev_shm`, and the cleanup/failure tests.
- No new credential-management dependency was introduced.

---

## 5. Execution-Plan Schema (`app/safety/plan_schema.py`)

`ExecutionParams` gained one field: `operation: str | None`, validated by a strict regex `^[a-z][a-z0-9_]{0,40}$` — **no whitespace, no shell metacharacters, no chaining/substitution** can ever appear. Membership in the approved allowlist is enforced by the Gateway, not the schema. `extra="forbid"` still rejects unknown fields.

---

## 6. Safety Gateway Integration (`app/safety/gateway.py`, `policy.py`)

`rat_related` is registered in `_ADAPTER_NAME → "remote_access"`. A new deterministic check **D2** runs after target authorization: for modules that take an operation (remote access), `plan.params.operation` must be in `policy.approved_operations(module)`, else **reject**. Policy gained `rat_related` branches for caps, enabled, availability, authorized targets, clamping, plus `approved_operations` / `requires_operation` / `is_operation_allowed`. A rejected plan creates **no registry record**, so it can never reach the adapter.

---

## 7. Kill-Switch Behaviour & Limitations

The adapter's subprocess runs through the existing managed-process mechanism, so an in-flight `nxc` call is in its own process group and is terminated by the unified kill switch (SIGTERM→grace→SIGKILL), with outcomes recorded. New executions are rejected while the kill switch is engaged (`test_killswitch_rejects_remote_access`).

**Documented limitation (honest):** terminating the local Kali `nxc` client does **not** guarantee cancellation of a request already accepted by the remote Windows management service. This is why every remote operation is **short, read-only and bounded** (default 30s cap) — there is no long-running or state-changing remote action to cancel. We do not claim guaranteed remote cancellation.

---

## 8. API Endpoints

- `POST /api/integrations/remote_access/run` — body `{operation, run_seconds?}`. Routed Request → schema → **Gateway** → Registry → Dispatcher → adapter. `423` on gateway rejection (disabled/unauthorized/unknown op/kill-switch), `422` on an unsafe operation token, `502` on adapter failure, else the structured result (credential-free).
- `GET /api/integrations/remote_access` — module status + approved operations (existing generic integration-status route).

The centralized `/api/operations/*` loop also drives this module (the planner can select it). No endpoint invokes NetExec directly or bypasses the Gateway.

---

## 9. Frontend Integration

New page `frontend/src/pages/RemoteAccess.tsx` (route `/remote-access`, nav "Remote Access"), reusing existing `ui.tsx` components. It shows the module title, ARMED/NOT ARMED/UNAVAILABLE status, protocol/target/creds-configured/caps, and the **approved operation identifiers** as selectable chips (with descriptions). "Run operation" calls the gateway-routed endpoint and renders the structured result: status pill (`success`/`auth_failed`/`unreachable`/`timed_out`), **measured facts**, message, duration. Honest states for unavailable/rejected/failed/success. It respects the global kill switch (button disabled + notice when halted). **No command input field, no shell, no credentials displayed.** `npm run typecheck` + `npm run build` pass.

---

## 10. Tests & Actual Results

```
cd backend && source .venv/bin/activate && python -m pytest tests/ -q
→ 118 passed, 1 warning in ~11s
```
`tests/test_remote_access.py` (37, incl. 8 remediation) covers the 22 required areas with mocks (canned NetExec output; no nxc run, no target): adapter init; missing credentials; missing dependency; invalid/unauthorized target; unknown operation; invalid params + **command-injection tokens rejected by schema**; **credential masking** (password absent from result even though NetExec echoed it); schema validation; gateway approval/rejection; kill-switch rejection; registry lifecycle; timeout; adapter failure; **secret-free audit**; planner integration (AI selects an operation id, target bound); analysis (facts vs objective); full feedback loop; **rejected plan never reaches the adapter**; API disabled→423, armed→200 (no secret leak), injection→422.

Runtime smoke (backend reloaded on :8077, nothing armed): `remote_access` available but **not runnable** (disabled); run→`423`; injection→`422`. Fail-closed confirmed.

Two Section-3 tests were updated (not weakened): they previously asserted `rat_related` is "not executable"; it is now a real, disabled-by-default module, so they assert it is rejected as **disabled** until armed.

---

## 11. Known Limitations

- **Mock-verified only.** No live NetExec run, no target contacted, no real auth. Live behaviour is **implemented but unverified**.
- **~~Password on local argv~~** — **REMEDIATED** (secure 0600 `/dev/shm` credential file; no argv exposure). See §4.
- **No guaranteed remote cancellation** — mitigated by short, read-only, bounded ops (§7).
- **Residual (LOW):** during the call the credential file exists on the Kali box (0600, RAM-backed, deleted immediately after). Root on the Kali box could read it — but root can read process memory anyway; this is not a new exposure.
- Operations are intentionally minimal (read-only info/connectivity). No state-changing admin actions by design.
- Synchronous execution (like the other adapters).

---

## 12. Live Verification Requirements

To move from mock-verified to live-verified (requires owner go-ahead):
1. An **authorized** Windows lab target IP, reachable from Kali, added to the allowlist.
2. Valid **lab credentials** in `.env` (`REMOTE_ACCESS_USER`/`PASSWORD`, optional `DOMAIN`).
3. `REMOTE_ACCESS_ENABLED=true` and an open SMB (445) / or WinRM (5985) service on the target.
4. Then a single `connectivity_check` confirms end-to-end, read-only.

---

### Verification legend
- **Mock verified:** adapter logic, gateway/operation allowlist, kill switch, planner/analysis/feedback integration, API, credential masking, frontend typecheck/build.
- **Implemented but unverified:** live NetExec auth/banner retrieval against a real Windows target.
- **Live verified:** none for this module.
- **Blocked:** live run (needs an authorized target + lab credentials + owner go-ahead).

See `docs/CHAKRAVYUH_MASTER_PROGRESS.md` for the cumulative record (Section 4 entry added).
