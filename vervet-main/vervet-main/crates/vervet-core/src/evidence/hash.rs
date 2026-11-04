//! Content-addressed evidence handles.

use serde::Serialize;

/// A content-addressed handle: the blake3 hash of a record's canonical JSON,
/// truncated to a short hex prefix for human and LLM readability.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Handle(String);

impl Handle {
    /// Compute the handle for any serializable value.
    pub fn of<T: Serialize>(value: &T) -> Result<Self, crate::Error> {
        let bytes = serde_json::to_vec(value)?;
        let hash = blake3::hash(&bytes);
        Ok(Handle(format!("ev:{}", &hash.to_hex()[..16])))
    }

    /// The handle string, e.g. `ev:1a2b3c4d5e6f7081`.
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl std::fmt::Display for Handle {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}
