//! The dense, read-first summary of an engagement.

use serde::Serialize;

/// The dense summary an AI consumer reads before pulling any handle. Carries
/// enough identity (name, attack id, tactic) that a receipt is self-describing
/// for reporting, with no registry lookup required.
#[derive(Clone, Debug, Serialize)]
pub struct Summary {
    /// The technique's human label.
    pub name: String,
    /// The ATT&CK technique id, e.g. `T1046`.
    pub attack_id: String,
    /// The tactic this technique advances, snake_case.
    pub tactic: String,
    /// The engagement this evidence belongs to.
    pub engagement_id: String,
    /// How many observations the handle map holds.
    pub observation_count: usize,
}
