# CHAKRAVYUH — AI Red Team Cyber Range Console

Academic project. An AI agent reads **real telemetry** from an isolated Windows
target VM, reasons over it with an LLM, and a dashboard shows three clearly
separated layers: **REAL LAB TELEMETRY**, **AGENT DECISION**, **ANALYSIS**.

## Safety boundary (read this)

This repository contains **no offensive execution code**. It does not open raw
sockets, generate traffic floods, perform credential stuffing against any
endpoint, or deploy any persistence / C2 mechanism.

- Every attack module's `execute()` is an explicit `NotImplementedError` stub.
  Wiring a real, authorized lab adapter is done by the operator *outside* this
  codebase.
- `discover / profile / plan / observe / adapt / analyze` only **read** real
  telemetry and reason about it. They never attack.
- The telemetry collector only **reads** system state (the same data Task
  Manager or `Get-WinEvent` shows). If a value is unavailable it returns
  `null` / `"unavailable"` — it never fabricates a number.

Run only against a machine you own or are authorized to monitor, on an isolated
host-only network.

## Layout

    backend/    FastAPI service: telemetry collector, DB, WebSocket, AI engine, module stubs
    frontend/   React + TypeScript + Tailwind dashboard
    docker-compose.yml

See `backend/README.md` for setup. For Docker, copy `.env.example` to `.env` and set
`POSTGRES_PASSWORD` before `docker compose up`.
