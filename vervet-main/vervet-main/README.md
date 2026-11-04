<p align="center">
  <img src="assets/vervet-github-hero.svg" alt="vervet: signed adversary emulation for AI security orchestration">
</p>

<p align="center">
  <a href="https://github.com/copyleftdev/vervet/actions/workflows/ci.yml"><img alt="CI workflow status" src="https://img.shields.io/github/actions/workflow/status/copyleftdev/vervet/ci.yml?branch=main&style=flat-square&label=ci"></a>
  <a href="Cargo.toml"><img alt="Rust MSRV 1.88" src="https://img.shields.io/badge/rust-1.88%2B-bf6f37?style=flat-square&labelColor=172023"></a>
  <a href="Cargo.toml"><img alt="Rust edition 2024" src="https://img.shields.io/badge/edition-2024-244148?style=flat-square&labelColor=172023"></a>
  <a href="LICENSE"><img alt="license AGPL-3.0-or-later" src="https://img.shields.io/badge/license-AGPL--3.0--or--later-6e9f98?style=flat-square&labelColor=172023"></a>
  <a href="#authorization-model"><img alt="security model: signed scope required" src="https://img.shields.io/badge/scope-Ed25519%20signed-f2c36b?style=flat-square&labelColor=172023"></a>
  <a href="#techniques"><img alt="MITRE ATT&CK techniques: 4" src="https://img.shields.io/badge/ATT%26CK-4%20techniques-c18453?style=flat-square&labelColor=172023"></a>
  <a href="#the-loop"><img alt="evidence schema vq1" src="https://img.shields.io/badge/evidence-vq1-8fbfb4?style=flat-square&labelColor=172023"></a>
</p>

<p align="center"><a href="https://tokentip.to/@copyleftdev"><img alt="Tip my tokens" src="https://tokentip.to/badge/copyleftdev.svg?logo=1"></a></p>

---

**vervet** is a single-binary adversary-emulation instrument for red teams,
purple teams, detection engineers, and AI/LLM security orchestrators. The model
decides the next step; vervet provides the narrow, typed, auditable primitive
that can actually run.

It is Infection Monkey inverted: no central server, no agent fleet, no hidden
control plane. The CLI is the contract. An orchestrator calls `describe`, fires
one authorized `emulate <ATTACK_ID>` verb, receives a vq1 evidence envelope,
and can fold receipts into ATT&CK coverage with `report`.

> **Authorized use only.** Every state-changing technique requires an
> Ed25519-signed scope manifest. Out-of-scope is a hard typed refusal: vervet
> cannot act against a target, technique, or time window the manifest does not
> authorize.

## At a glance

| Surface | What matters |
|---|---|
| Runtime | Rust 2024 workspace, CLI-first, no server required |
| Orchestrator contract | `describe` exposes verbs, techniques, and required inputs |
| Authorization | Ed25519-signed manifest checked before every state-changing action |
| Evidence | vq1 receipts with content-addressed handles |
| Auditability | blake3-linked audit entries make timeline edits visible |
| Coverage | `report` folds receipts into MITRE ATT&CK tactics and techniques |
| Safety posture | Out-of-scope requests fail closed with typed denial and exit code `2` |

## Design center

Modern AI agents can plan a security engagement, but they still need a narrow
execution layer with real boundaries. vervet is built around three constraints:

| Constraint | Implementation |
|---|---|
| An LLM should know exactly what it can call | `vervet describe` emits the machine-readable contract |
| A technique should not run by convention | `Gate::authorize` mints an unforgeable `Grant` required by techniques |
| Evidence should survive scrutiny | Receipts carry typed summaries and audit entries linked to predecessor handles |

## The loop

```text
signed scope manifest
        |
        v
describe -> emulate <ATTACK_ID> -> receipt.vq1 -> report
              |                    |
              |                    +-- content-addressed evidence
              +-- authorize -> engage -> emit
```

Every state-changing path flows through `authorize -> engage -> emit`. That is
the core property of the project: the same boundary governs network discovery,
remote-service checks, valid-account assertions, and password-spray emulation.

### 1. Sign a scope manifest

A manifest is the signed authorization for one engagement: which CIDRs, which
techniques, and which time window. The signing key is held by the authorizing
party, never by vervet.

```json
{
  "engagement_id": "acme-2026-q2",
  "operator": "dj@codetestcode.io",
  "authorized_cidrs": ["10.10.0.0/24"],
  "excluded_cidrs": ["10.10.0.1/32"],
  "technique_allowlist": ["T1046", "T1110.003"],
  "valid_from": 0,
  "valid_until": 4102444800
}
```

```sh
cargo run -p vervet-scope --example sign -- <seed-hex-32-bytes> claims.json > manifest.json
```

The command prints the authority public key to stderr. That authority is passed
out-of-band to the gate; a key embedded in the manifest would be self-signed and
therefore forgeable.

### 2. Discover the contract

```sh
vervet describe
```

```jsonc
{
  "tool": "vervet",
  "protocol": { "schema": "vq1", "version": "0.1.0" },
  "verbs": ["describe", "schema", "emulate", "report", "explain", "help"],
  "authorization": "every engagement requires an Ed25519-signed scope manifest",
  "techniques": [
    {
      "id": "T1046",
      "name": "Network Service Discovery",
      "tactic": "discovery",
      "inputs": ["target", "ports (default 445,22,3389 = SMB,SSH,RDP)"]
    }
  ]
}
```

### 3. Emulate one technique

```sh
vervet emulate T1046 \
  --manifest manifest.json \
  --authority 4cb5abf6ad79fbf5abbccafcc269d85cd2651ed4b885b5869f241aedf0a5ba29 \
  --target 10.10.0.5 \
  --ports 22,80 \
  --store ./runs
```

The output is a receipt: a vq1 evidence envelope plus the audit chain that
records authorization and engagement as linked actions.

```jsonc
{
  "envelope": {
    "header": { "schema": "vq1", "version": "0.1.0" },
    "summary": {
      "name": "Network Service Discovery",
      "attack_id": "T1046",
      "tactic": "discovery",
      "engagement_id": "acme-2026-q2",
      "observation_count": 0
    },
    "handles": {}
  },
  "audit": [
    {
      "seq": 0,
      "engagement_id": "acme-2026-q2",
      "action": "authorize T1046 target=10.10.0.5",
      "prev": "ev:genesis"
    },
    {
      "seq": 1,
      "engagement_id": "acme-2026-q2",
      "action": "engage T1046 observations=0",
      "prev": "ev:412c0a8637502e7a"
    }
  ]
}
```

Requests outside the manifest fail closed with exit code `2`:

```sh
denied: target is not within any authorized CIDR
denied: target falls within an excluded CIDR
denied: technique is not in the manifest allowlist
```

### 4. Report coverage

```sh
vervet report --store ./runs --engagement acme-2026-q2
```

```jsonc
{
  "schema": "vq1-coverage",
  "tactics": { "discovery": ["T1046"] },
  "techniques": [
    {
      "id": "T1046",
      "name": "Network Service Discovery",
      "tactic": "discovery",
      "engagements": 1,
      "observations": 0,
      "detection": "unobserved"
    }
  ],
  "totals": { "engagements": 1, "techniques": 1, "observations": 0 },
  "detection_note": "detection is unobserved — vervet does not see your blue team; feed SIEM evidence to populate"
}
```

## Verbs

The CLI surface is intentionally small enough for an agent to reason about and
strict enough for a human operator to audit.

| verb | purpose |
|---|---|
| `describe` | Emit the machine-readable protocol, verbs, and technique inputs |
| `schema` | Print the engagement-receipt contract as JSON Schema |
| `emulate <ATTACK_ID>` | Authorize, fire one technique, and emit an audited receipt |
| `report <receipts...>` | Fold receipts into ATT&CK coverage, or read from `--store` |
| `explain` | Resolve one evidence handle from a receipt |
| `help` | Human-facing CLI help; `-V` / `--version` for version output |

## Techniques

The current registry is deliberately compact. Each entry maps to MITRE ATT&CK
and is implemented as one reviewed, in-tree primitive.

| ATT&CK id | name | tactic |
|---|---|---|
| `T1046` | Network Service Discovery | discovery |
| `T1021` | Remote Services | lateral movement |
| `T1078` | Valid Accounts | initial access |
| `T1110.003` | Password Spraying | credential access |

Each technique is one self-contained file in `vervet-techniques/src/`. Adding a
technique means adding that file plus one `mod` line; `describe`, `schema`, and
dispatch read the registry.

## Authorization model

- **`Grant` is unforgeable.** It has no public constructor; only
  `vervet_scope::Gate::authorize` mints one.
- **Techniques cannot bypass scope.** A technique takes `&Grant`, so acting
  outside an approved manifest is blocked by the type system.
- **Registration is compile-time only.** Techniques register through
  `inventory`; there is no dynamic plugin loading.
- **The audit chain is tamper-evident.** Each entry commits to the previous
  entry's blake3 handle, so removal or mutation breaks every later link.

## Credential verification

Credential-access techniques judge attempts through a pluggable `Verifier`.

The default build ships protocol-level probes only. The SSH probe performs a
real RFC-4253 version exchange, confirms the service, and captures its banner,
but reaches at most `ssh_confirmed`; it does not assert credential validity.

The `--features ssh-auth` build adds `SshAuth`, a credential-asserting backend
that performs real password authentication through `ssh2` and returns
`valid` / `invalid`. Password material is never written to evidence.

## Build

Default builds stay lean and protocol-level. Credential-asserting SSH is
available, but it is an explicit feature flag.

```sh
cargo build --release
cargo build --release -p vervet-cli --features ssh-auth
```

Requires Rust 1.88+ with edition 2024. The default binary is dependency-light
and ships protocol probes only; `ssh-auth` is opt-in so the default stays lean.

## Test

The default suite is hermetic: no Docker and no external services.

```sh
cargo test --workspace
cargo test -p vervet-scope
```

Docker-gated credential tests exercise the real SSH backend and full
`authorize -> engage -> emit` pipeline:

```sh
cargo test -p vervet-verify --features ssh-auth
cargo test -p vervet-e2e --features ssh-auth
cargo test -p vervet-cli --features ssh-auth
```

## Crate layout

| crate | purpose |
|---|---|
| `vervet-core` | Foundational types: ATT&CK ids, vq1 envelopes, content-addressed evidence |
| `vervet-scope` | Signed manifests, IPv4 CIDR scope, unforgeable grants, audit chains |
| `vervet-technique` | The `Technique` trait plus the `inventory` registry |
| `vervet-techniques` | One self-contained implementation file per ATT&CK technique |
| `vervet-verify` | Pluggable backends that judge an attempt into a `Verdict` |
| `vervet-engage` | The one path every technique firing uses: authorize -> engage -> emit |
| `vervet-report` | Pure JSON coverage aggregation from receipts |
| `vervet-store` | Content-addressed run store under `<root>/<engagement>/<run-id>.json` |
| `vervet-cli` | The verb surface |
| `vervet-e2e` | Docker-backed end-to-end tests against real services |

## Invariants

- **One concept per file.** `mod.rs` only re-exports, and CI enforces a 200-line
  source budget through `scripts/check-line-budget.sh`.
- **Receipts are self-describing.** `report` does not need registry lookup; the
  summary carries the technique name, ATT&CK id, and tactic.
- **Detection is never overstated.** vervet reports `unobserved`, never
  `undetected`, because it cannot see your blue team.

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE).

---

<sub><strong>Topics:</strong> adversary-emulation · breach-and-attack-simulation · MITRE ATT&CK · red-team · purple-team · detection-engineering · security-automation · Rust · CLI · AI · LLM-agent · cybersecurity</sub>
