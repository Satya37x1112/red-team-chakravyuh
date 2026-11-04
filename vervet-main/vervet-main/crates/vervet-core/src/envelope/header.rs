//! The protocol identity stamped on every envelope.

use serde::Serialize;

/// The protocol identity carried by every vq1 envelope.
#[derive(Clone, Copy, Debug, Serialize)]
pub struct Header {
    /// The protocol name — `vq1`.
    pub schema: &'static str,
    /// The protocol version this envelope conforms to.
    pub version: &'static str,
}

impl Header {
    /// The current protocol identity.
    pub const VQ1: Header = Header {
        schema: "vq1",
        version: "0.1.0",
    };
}

impl Default for Header {
    fn default() -> Self {
        Header::VQ1
    }
}
