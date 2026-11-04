//! `vervet schema` — the engagement receipt contract as JSON Schema.

use std::process::ExitCode;

use serde_json::json;

/// Emit the receipt contract, pinned to the protocol version. A receipt is a
/// vq1 evidence envelope bound to a tamper-evident audit chain.
pub fn run() -> ExitCode {
    let envelope = json!({
        "type": "object",
        "required": ["header", "summary", "handles"],
        "properties": {
            "header": {
                "type": "object",
                "properties": {
                    "schema": { "const": "vq1" },
                    "version": { "const": "0.1.0" }
                }
            },
            "summary": {
                "type": "object",
                "properties": {
                    "name": { "type": "string" },
                    "attack_id": { "type": "string" },
                    "tactic": { "type": "string" },
                    "engagement_id": { "type": "string" },
                    "observation_count": { "type": "integer" }
                }
            },
            "handles": {
                "type": "object",
                "description": "map of ev:<hash> to one observation record"
            }
        }
    });
    let audit = json!({
        "type": "array",
        "description": "tamper-evident chain; audit[n].prev is the blake3 handle of audit[n-1]",
        "items": {
            "type": "object",
            "properties": {
                "seq": { "type": "integer" },
                "engagement_id": { "type": "string" },
                "action": { "type": "string" },
                "prev": { "type": "string" }
            }
        }
    });
    let schema = json!({
        "$id": "https://vervet.tools/schema/vq1-receipt/0.1.0",
        "title": "vervet engagement receipt",
        "type": "object",
        "required": ["envelope", "audit"],
        "properties": { "envelope": envelope, "audit": audit }
    });
    println!(
        "{}",
        serde_json::to_string_pretty(&schema).expect("schema serialize")
    );
    ExitCode::SUCCESS
}
