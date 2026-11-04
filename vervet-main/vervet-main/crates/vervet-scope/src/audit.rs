//! Tamper-evident audit chain for engagement actions.

use serde::Serialize;
use vervet_core::evidence::Handle;

/// One tamper-evident audit entry. Each entry commits to the previous entry's
/// handle, forming a hash chain: altering any past entry breaks every link
/// after it.
#[derive(Clone, Debug, Serialize)]
pub struct AuditEntry {
    /// Position of this entry in the chain, from zero.
    pub seq: u64,
    /// The engagement this action belongs to.
    pub engagement_id: String,
    /// What happened, as a short action token.
    pub action: String,
    /// Handle of the previous entry, committing this one to the chain.
    pub prev: String,
}

impl AuditEntry {
    /// The handle used as `prev` for the first entry in a chain.
    pub const GENESIS: &'static str = "ev:genesis";

    /// Append an action to the chain, returning the entry and its own handle
    /// (which the next entry should pass as `prev`).
    pub fn append(seq: u64, engagement_id: &str, action: &str, prev: &str) -> (AuditEntry, Handle) {
        let entry = AuditEntry {
            seq,
            engagement_id: engagement_id.to_string(),
            action: action.to_string(),
            prev: prev.to_string(),
        };
        let handle = Handle::of(&entry).expect("audit entry serialize");
        (entry, handle)
    }
}
