//! The MITRE ATT&CK technique identifier newtype.

use serde::Serialize;

/// A MITRE ATT&CK technique identifier, e.g. `T1046`.
///
/// Backed by a `&'static str` so a registered technique can declare its
/// identifier as a `const` with no allocation. Serializes transparently to the
/// bare identifier string.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize)]
pub struct TechniqueId(pub &'static str);

impl TechniqueId {
    /// The bare ATT&CK identifier, e.g. `"T1046"`.
    pub const fn as_str(&self) -> &'static str {
        self.0
    }
}

impl std::fmt::Display for TechniqueId {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.0)
    }
}
