# CYBER CHAKRAVYUH — Executive Overview

**Baseline:** branch `main`, HEAD `39c5233` · Backend `http://127.0.0.1:8077` · Frontend `http://127.0.0.1:5173` · **249 backend tests passing** · Verdict: **READY WITH LIMITATIONS**.

## 30-second explanation
CYBER CHAKRAVYUH is an AI-assisted Red-Team-vs-Blue-Team lab platform that runs entirely from Kali Linux. An operator drives a React dashboard; an AI planner *proposes* bounded security assessments; a deterministic Python backend *validates, authorizes, executes, and audits* them through a single Safety Gateway. The AI never touches tools directly — it only suggests; the backend decides.

## 2-minute explanation
The project addresses a real risk in "AI that does security work": an LLM that can run attack tools is dangerous if it hallucinates or is manipulated. CHAKRAVYUH separates **intelligence** (the LLM planner) from **execution** (deterministic Python) and **authorization** (a fail-closed Safety Gateway). The operator discovers lab hosts over Tailscale, explicitly selects and authorizes a target (discovered ≠ authorized), and runs bounded, read-only or capped operations (reconnaissance, Hydra auth-testing, Locust load-testing, NetExec remote read-only ops). Every operation is checked against a central allowlist, respects a global kill switch, and is written to a SQLite audit trail. A Blue-Team/SOC (Wazuh on the target side) can then *detect* the generated activity — that detection is the "proof" and is external to this codebase. Today the platform's safety controls, discovery, selection, kill-switch and audit are **live-verified**; live Windows-target checks and AI inference are **blocked** by two external dependencies.

## 5-minute technical explanation
- **What it is:** FastAPI backend + React/TS/Vite frontend. Centralized LLM client (`app/integrations/_llm.py`) via OpenRouter (model `anthropic/claude-sonnet-4.5`), optional OmniRoute gateway.
- **AI-assisted:** the planner (`app/agent/planner.py`) turns an operator objective into a **structured Pydantic ExecutionPlan** (`app/safety/plan_schema.py`). It cannot set caps or authorize itself.
- **Deterministic safety:** the **Safety Gateway** (`app/safety/gateway.py` `evaluate()`) checks, fail-closed and in order: kill-switch → module enabled → adapter available → **target allowlist** → operation allowlist → parameter clamping → concurrency, then creates an **Execution Registry** record. The **Dispatcher** (`app/safety/dispatcher.py`) is the only path from an approved record to a real **adapter** (Hydra/Locust/NetExec).
- **Red Team modules:** Network Discovery (`app/services/discovery.py`), Hydra auth-testing (`app/integrations/hydra.py`), Locust load/`locust_sim` simulation, NetExec 5 read-only ops (`app/integrations/remote_access.py`), offline hash-audit (`app/services/hash_audit.py`), authenticated file transfer (`app/services/transfer.py`).
- **Blue Team:** detection occurs on the **target's own SOC/Wazuh** — CHAKRAVYUH has **no event-forwarding code**; it generates OS-level activity the SOC collects. UBA scoring (`app/modules/uba.py`) runs over available telemetry.
- **Honesty:** results are labeled measured / mocked / simulation / unavailable; a probe to an offline host reports "unreachable", never fabricated open ports.
- **What's demonstrable today:** discovery, explicit authorization + hotspot/public rejection, bounded recon probe, kill-switch + re-arm, audit trail, DDoS **simulation** (no traffic), 249 passing tests.
- **Blocked:** Windows target `opensoc-windows`/`100.80.167.51` offline → NetExec/file-transfer/live-connectivity not live-verified; OpenRouter auth failing → AI planning falls back deterministically (labeled FALLBACK).
