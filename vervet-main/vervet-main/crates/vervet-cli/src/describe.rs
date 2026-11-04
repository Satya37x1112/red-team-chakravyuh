//! `vervet describe` — the self-describing contract.

use std::process::ExitCode;

use serde_json::json;
use vervet_technique::all;

/// Emit protocol identity, the verb surface, and every registered technique
/// with its ATT&CK id and footprint. An AI consumer calls this once to
/// bootstrap — no external docs required.
pub fn run() -> ExitCode {
    let techniques: Vec<_> = all().map(|t| t.meta()).collect();
    let doc = json!({
        "tool": "vervet",
        "protocol": { "schema": "vq1", "version": "0.1.0" },
        "verbs": ["describe", "schema", "emulate", "report", "explain", "help"],
        "output": "emulate emits a receipt (vq1 envelope + audit chain); report folds receipts into an ATT&CK coverage map",
        "authorization": "every engagement requires an Ed25519-signed scope manifest",
        "techniques": techniques,
    });
    println!(
        "{}",
        serde_json::to_string_pretty(&doc).expect("describe serialize")
    );
    ExitCode::SUCCESS
}
