# CYBER CHAKRAVYUH — Presentation Outline (15 slides)

Each slide: **Key message · points · diagram/screenshot · presenter note · likely panel Q.**

1. **Title / Intro** — "AI Red Team vs AI Blue Team, Kali-only." Points: theme, team, baseline `39c5233`, 249 tests. *Screenshot: dashboard.* Q: "What's novel here?"
2. **Problem statement** — "LLMs that run attack tools are dangerous if hallucinating/manipulated." Points: autonomy risk, authorization gap, auditability. Q: "Why not just let the AI run tools?"
3. **Objectives** — safe AI-assisted assessment; separation of intelligence/execution/authorization; auditable, bounded. Q: "How do you measure success?"
4. **Overall architecture** — Dashboard→FastAPI→Planner→Plan→Gateway→Registry→Dispatcher→Adapter→Telemetry→Audit. *Mermaid flow.* Q: "Which parts are real vs conceptual?"
5. **AI planner vs deterministic execution** — AI proposes structured plans; backend validates/authorizes/executes. Points: `planner.py`, `plan_schema.py` (no caps field), fallback. Q: "Can the AI widen a limit?"
6. **Safety Gateway & authorization** — fail-closed `evaluate()`: kill-switch→enabled→adapter→target allowlist→op allowlist→caps→concurrency. *Code excerpt.* Q: "Where exactly is authorization enforced?"
7. **Network Discovery** — tailnet enum, pending vs authorized, dynamic hotspot protection. *Discovery page.* Q: "What stops you scanning the shared Wi-Fi?"
8. **Red Team modules** — Hydra (bounded auth), Locust (capped load + simulation), NetExec (5 read-only ops). Q: "Is this a real DDoS?"
9. **Blue Team & telemetry** — external SOC/Wazuh detects generated activity; measured vs simulated vs unavailable. *Event-flow table.* Q: "Does Wazuh actually receive events?"
10. **UBA & audit logging** — SQLite audit, secret masking, UBA scoring. Q: "What's in an audit record?"
11. **Live demonstration** — recon + safety controls (harmless). *Live.* Q: "Show a blocked operation."
12. **Testing & verification** — 249 passing, typecheck+build green, live safety checks. *pytest output.* Q: "Any skipped/failed tests?"
13. **Limitations** — Windows offline, OpenRouter auth, non-unified routes, no Wazuh code. Q: "What isn't live-verified?"
14. **Future scope** — pipeline unification, Wazuh connector, live telemetry, multi-provider fallback. Q: "What would you build next?"
15. **Conclusion** — safe, auditable, honest; READY WITH LIMITATIONS. Q: "Is it production-ready?" (No — lab demo.)
