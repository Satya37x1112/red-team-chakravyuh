//! The coverage map types emitted by a report.

use std::collections::BTreeMap;

use serde::Serialize;

/// Per-technique rollup across all receipts that exercised it.
#[derive(Clone, Debug, Serialize)]
pub struct TechniqueCoverage {
    /// The ATT&CK technique id, e.g. `T1046`.
    pub id: String,
    /// The technique's human label.
    pub name: String,
    /// The tactic this technique advances.
    pub tactic: String,
    /// How many distinct engagements exercised it.
    pub engagements: u64,
    /// Total observations it produced across those engagements.
    pub observations: u64,
    /// Always `unobserved` in v0: vervet fires techniques but does not see the
    /// defender, so it never claims a technique was detected or missed.
    pub detection: &'static str,
}

/// Workspace-wide totals.
#[derive(Clone, Debug, Serialize)]
pub struct Totals {
    /// Distinct engagements seen across all receipts.
    pub engagements: u64,
    /// Distinct techniques exercised.
    pub techniques: usize,
    /// Total observations across every receipt.
    pub observations: u64,
}

/// An ATT&CK coverage map: techniques grouped under the tactics they advance.
#[derive(Clone, Debug, Serialize)]
pub struct Coverage {
    /// The protocol name — `vq1-coverage`.
    pub schema: &'static str,
    /// The coverage-map schema version.
    pub version: &'static str,
    /// tactic -> the technique ids exercised under it.
    pub tactics: BTreeMap<String, Vec<String>>,
    /// Per-technique rollups across all receipts.
    pub techniques: Vec<TechniqueCoverage>,
    /// Workspace-wide totals.
    pub totals: Totals,
    /// Honest note that detection is unobserved, not undetected.
    pub detection_note: &'static str,
}

impl Coverage {
    /// Stamp the protocol identity and honest detection note onto a rollup.
    pub fn new(
        techniques: Vec<TechniqueCoverage>,
        tactics: BTreeMap<String, Vec<String>>,
        totals: Totals,
    ) -> Self {
        Coverage {
            schema: "vq1-coverage",
            version: "0.1.0",
            tactics,
            techniques,
            totals,
            detection_note: "detection is unobserved — vervet does not see your \
blue team; feed SIEM evidence to populate",
        }
    }
}
