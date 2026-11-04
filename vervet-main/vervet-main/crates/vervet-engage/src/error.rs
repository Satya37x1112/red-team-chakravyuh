//! The error type for an engagement run.

use vervet_scope::Denied;

/// Why an engagement could not produce a receipt.
#[derive(Debug)]
pub enum EngageError {
    /// Authorization was refused by the gate.
    Denied(Denied),
    /// Evidence could not be assembled into an envelope.
    Assembly(vervet_core::Error),
}

impl std::fmt::Display for EngageError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            EngageError::Denied(d) => write!(f, "denied: {d}"),
            EngageError::Assembly(e) => write!(f, "assembly failed: {e}"),
        }
    }
}

impl std::error::Error for EngageError {}

impl From<vervet_core::Error> for EngageError {
    fn from(e: vervet_core::Error) -> Self {
        EngageError::Assembly(e)
    }
}
