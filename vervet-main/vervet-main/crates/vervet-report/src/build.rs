//! Folding receipts into a coverage map.

use std::collections::BTreeMap;

use serde_json::Value;

use crate::coverage::{Coverage, TechniqueCoverage, Totals};

const DETECTION: &str = "unobserved";

/// Accumulated rollup for one technique id.
struct Acc {
    name: String,
    tactic: String,
    engagements: u64,
    observations: u64,
}

/// Aggregate engagement receipts into an ATT&CK coverage map. Receipts whose
/// summary cannot be located are skipped (honest emptiness over guessing).
pub fn coverage(receipts: &[Value]) -> Coverage {
    let mut by_id: BTreeMap<String, Acc> = BTreeMap::new();

    for receipt in receipts {
        let Some(summary) = summary_of(receipt) else {
            continue;
        };
        let id = str_at(summary, "attack_id")
            .unwrap_or("unknown")
            .to_string();
        let acc = by_id.entry(id.clone()).or_insert_with(|| Acc {
            name: str_at(summary, "name").unwrap_or(&id).to_string(),
            tactic: str_at(summary, "tactic").unwrap_or("unknown").to_string(),
            engagements: 0,
            observations: 0,
        });
        acc.engagements += 1;
        acc.observations += summary
            .get("observation_count")
            .and_then(Value::as_u64)
            .unwrap_or(0);
    }

    let mut techniques = Vec::new();
    let mut tactics: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for (id, acc) in &by_id {
        tactics
            .entry(acc.tactic.clone())
            .or_default()
            .push(id.clone());
        techniques.push(TechniqueCoverage {
            id: id.clone(),
            name: acc.name.clone(),
            tactic: acc.tactic.clone(),
            engagements: acc.engagements,
            observations: acc.observations,
            detection: DETECTION,
        });
    }

    let totals = Totals {
        engagements: techniques.iter().map(|t| t.engagements).sum(),
        techniques: techniques.len(),
        observations: techniques.iter().map(|t| t.observations).sum(),
    };
    Coverage::new(techniques, tactics, totals)
}

/// Locate the summary in a receipt, tolerating a bare envelope.
fn summary_of(receipt: &Value) -> Option<&Value> {
    receipt
        .get("envelope")
        .and_then(|e| e.get("summary"))
        .or_else(|| receipt.get("summary"))
}

fn str_at<'a>(v: &'a Value, key: &str) -> Option<&'a str> {
    v.get(key).and_then(Value::as_str)
}
