//! Self-describing technique metadata.

use serde::Serialize;
use vervet_core::attack::{Tactic, TechniqueId};

/// What footprint a technique leaves, surfaced in `describe` so an operator and
/// the AI can reason about blast radius before engaging.
#[derive(Clone, Copy, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SideEffect {
    /// Observes only; opens no connections that mutate target state.
    ReadOnly,
    /// Establishes connections a target may log or alert on.
    Observable,
}

/// Static description of a technique, declared as a `const` in each technique
/// file and emitted verbatim by `describe`.
#[derive(Clone, Copy, Debug, Serialize)]
pub struct TechniqueMeta {
    /// The ATT&CK technique id, e.g. `T1046`.
    pub id: TechniqueId,
    /// The tactic this technique advances.
    pub tactic: Tactic,
    /// Human label for the technique.
    pub name: &'static str,
    /// One-line description of what it does.
    pub summary: &'static str,
    /// The footprint it leaves on the target.
    pub side_effect: SideEffect,
    /// Human/LLM-readable list of the inputs this technique consumes, so a
    /// consumer of `describe` knows what to pass to `emulate`.
    pub inputs: &'static [&'static str],
}
