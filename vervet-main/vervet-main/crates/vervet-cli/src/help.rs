//! `vervet help` — the human-facing verb surface. The machine-readable
//! counterpart is `vervet describe`.

use std::process::ExitCode;

const HELP: &str = "\
vervet — AI-native adversary-emulation instrument

USAGE:
    vervet <verb> [args]

VERBS:
    describe              List the protocol, verbs, and every registered technique (JSON)
    schema               Print the engagement-receipt contract as JSON Schema
    emulate <ATTACK_ID>  Authorize and fire a technique, emitting an audited receipt
    report <receipts>    Fold receipts into an ATT&CK coverage map
    explain              Resolve one evidence handle from a receipt

OPTIONS:
    -h, --help           Show this help
    -V, --version        Show the version

Every state-changing engagement requires an Ed25519-signed scope manifest;
out-of-scope is a hard, typed refusal (exit 2). Run `vervet describe` for the
machine-readable contract — each technique lists the `inputs` it expects.";

/// Print the top-level help to stdout and succeed.
pub fn run() -> ExitCode {
    println!("{HELP}");
    ExitCode::SUCCESS
}
