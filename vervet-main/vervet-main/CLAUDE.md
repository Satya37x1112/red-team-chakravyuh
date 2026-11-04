# vervet

An AI-native adversary-emulation instrument. Infection Monkey, inverted: the
LLM is the orchestrator, vervet is a fleet of atomic, deterministic emulation
primitives that emit a typed evidence envelope (vq1). The CLI **is** the
contract — no Island, no server, no MCP glue.

**Authorized use only.** Every state-changing technique requires an
Ed25519-signed scope manifest. Out-of-scope is a hard, typed refusal.

## Crate layout

| crate | purpose |
|---|---|
| `vervet-core` | foundational types: ATT&CK ids, the vq1 envelope, content-addressed evidence |
| `vervet-scope` | authorization spine: signed `Manifest`, IPv4 CIDR scope, the unforgeable `Grant` token, audit chain |
| `vervet-technique` | the `Technique` trait + `inventory` registry (self-registration) |
| `vervet-techniques` | the techniques themselves — one self-contained file per ATT&CK id (T1078 valid accounts, T1046 discovery, T1021 remote services, T1110.003 password spray) |
| `vervet-verify` | the auth-verifier seam: pluggable backends (reachability, real SSH protocol probe) that judge an attempt → `Verdict` |
| `vervet-engage` | orchestration: authorize → engage → emit an audited `Receipt` (the one path every technique-firing verb funnels through) |
| `vervet-report` | fold receipts into an ATT&CK coverage map — pure JSON aggregation, no registry lookup |
| `vervet-store` | content-addressed run store: persist receipts under `<root>/<engagement>/<run-id>.json` |
| `vervet-cli` | the verb surface: `describe`, `schema`, `emulate`, `report`, `explain`, `help` |
| `vervet-e2e` | Docker-backed end-to-end tests: drive the full pipeline against real services (no library code) |

`emulate <ATTACK_ID>` drives *any* registered technique — adding a technique
needs no CLI change. It emits a **Receipt**: a vq1 evidence envelope bound to a
tamper-evident audit chain. Each `audit[n].prev` is the blake3 handle of
`audit[n-1]`, so any removed or altered action breaks every later link.
`describe` lists each technique's `inputs` so a consumer knows what to pass.

Receipts are **self-describing**: the summary carries the technique name, ATT&CK
id and tactic, so `report <receipt...>` rolls them into a coverage map grouped
by tactic with no registry lookup. Detection is reported as `unobserved`, never
`undetected` — vervet doesn't see your blue team.

Receipts can be **persisted**: `emulate --store <dir>` (or `VERVET_STORE`) writes
each receipt to a content-addressed run store grouped by engagement, and
`report --store <dir> [--engagement <id>]` aggregates them with no file-piping —
the loop an AI orchestrator drives across many engagements.

Credential-access techniques judge attempts through the `Verifier` seam. The
default build ships protocol-level probes only — the SSH probe does a real
RFC-4253 version exchange to confirm the service and capture its banner, but
reaches at most `ssh_confirmed`.

The `--features ssh-auth` build adds `SshAuth`, a credential-asserting backend
(libssh2 via `ssh2`) that performs real password auth and returns
`valid`/`invalid`; the spray uses it on SSH ports when the feature is on. It is
opt-in so the default binary stays lean and static. Password material is never
written to evidence regardless of verdict.

The credential path is proven end to end against real containerized services
(testcontainers, all Docker-gated and out of the default suite): `vervet-verify
--features ssh-auth` exercises the `SshAuth` backend against a real sshd;
`vervet-e2e --features ssh-auth` drives the full `authorize → engage → emit`
pipeline; `vervet-cli --features ssh-auth` drives the compiled binary
black-box through `emulate → store → report`. The container's sshd is pinned to
an SSH port (a dynamic host port would fall through to a reachability probe,
since `judge` selects the SSH backend by port).

## Invariants

- **`Grant` is unforgeable.** It has no public constructor; only
  `vervet_scope::Gate::authorize` mints one. A technique takes `&Grant`, so it
  cannot act outside an approved scope. This is enforced by the type system.
- **Compile-time registration only.** Techniques register via `inventory` — no
  dynamic plugin loading, so every technique is in-tree, reviewed, and gated.
- **Add a technique = add one file** in `vervet-techniques/src/` plus one `mod`
  line. `describe`, `schema` and dispatch read the registry; nothing else
  changes.
- **One concept per file; `mod.rs` only re-exports.** Enforced in CI by
  `scripts/check-line-budget.sh` — no source file may exceed 200 lines.

## Honest limits

Live network observations are timestamped facts, not bitwise-reproducible.
`emulate` cannot know whether your blue team saw it — evidence is marked
`unobserved`, never `undetected`.
