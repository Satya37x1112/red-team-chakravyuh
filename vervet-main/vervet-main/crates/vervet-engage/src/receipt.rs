//! The top-level artifact of an engagement: evidence plus its audit chain.

use serde::Serialize;
use vervet_core::envelope::Envelope;
use vervet_scope::AuditEntry;

/// An engagement receipt: the vq1 evidence envelope bound to a tamper-evident
/// audit chain. Each `audit[n].prev` is the blake3 handle of `audit[n-1]`, so
/// removing or altering any action breaks every link after it.
#[derive(Clone, Debug, Serialize)]
pub struct Receipt {
    /// The vq1 evidence envelope produced by the engagement.
    pub envelope: Envelope,
    /// The hash chain of actions that produced the evidence.
    pub audit: Vec<AuditEntry>,
}
