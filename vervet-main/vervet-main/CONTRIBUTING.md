# Contributing to vervet

vervet is an AI-native adversary-emulation instrument. The CLI **is** the
contract, so the bar for changes is correctness, honesty, and small surface.

## Ground rules

- **Authorized use only.** Every state-changing technique acts behind an
  Ed25519-signed scope manifest. Never weaken the gate, and never let a
  technique act without a `&Grant`.
- **Honesty in evidence.** Report what was observed. Detection is `unobserved`,
  never `undetected` — vervet does not see the blue team. Never write credential
  material into evidence.

## Invariants the CI enforces

- **One concept per file; `mod.rs` only re-exports.** No source file may exceed
  200 lines (`scripts/check-line-budget.sh`). A file over budget is doing two
  jobs — split it.
- **Add a technique = add one file** in `vervet-techniques/src/` plus one `mod`
  line. Techniques self-register via `inventory`; `describe`, `schema`, and
  dispatch read the registry, so nothing else changes. No dynamic plugin
  loading — every technique is in-tree, reviewed, and gated.
- **Documented public API.** Library crates carry `#![deny(missing_docs)]`;
  every public item needs a doc comment.

## Before you open a PR

Run the same gates CI does:

```sh
bash scripts/check-line-budget.sh 200
cargo fmt --all --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```

If you touch the credential path, also run the Docker-backed end-to-end suites
(opt-in, need Docker):

```sh
cargo test -p vervet-verify --features ssh-auth   # the SshAuth backend
cargo test -p vervet-e2e    --features ssh-auth   # the full pipeline
cargo test -p vervet-cli    --features ssh-auth   # the binary, black-box
```

## Commits

Keep commits focused and the message explaining the *why*. The default branch
is `main`; CI runs on every push and pull request.
