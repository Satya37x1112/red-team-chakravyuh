//! The single error type shared across vervet-core.

use std::fmt;

/// Errors raised while assembling or hashing evidence.
#[derive(Debug)]
pub enum Error {
    /// A value could not be serialized to canonical JSON.
    Serialize(serde_json::Error),
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::Serialize(e) => write!(f, "evidence serialization failed: {e}"),
        }
    }
}

impl std::error::Error for Error {}

impl From<serde_json::Error> for Error {
    fn from(e: serde_json::Error) -> Self {
        Error::Serialize(e)
    }
}
