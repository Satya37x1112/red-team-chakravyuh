//! The verdict spectrum an auth verifier can return.

use serde::Serialize;

/// The outcome of judging one authentication attempt. The spectrum is honest
/// about partial knowledge: a probe backend reaches at most `ServiceConfirmed`,
/// while a credential-asserting backend can return `Valid` / `Invalid`.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Verdict {
    /// No TCP connection could be established.
    Unreachable,
    /// Connected, but the service is not the expected protocol.
    NotSsh,
    /// The expected service was confirmed by protocol banner.
    ServiceConfirmed {
        /// The version banner the service announced.
        banner: String,
    },
    /// Credentials authenticated (reserved for a credential-asserting backend).
    Valid,
    /// Credentials were rejected (reserved for a credential-asserting backend).
    Invalid,
    /// Connected, but credentials were not asserted by any backend.
    Unverified,
}

impl Verdict {
    /// A compact token for evidence rendering.
    pub fn kind(&self) -> &'static str {
        match self {
            Verdict::Unreachable => "unreachable",
            Verdict::NotSsh => "not_ssh",
            Verdict::ServiceConfirmed { .. } => "ssh_confirmed",
            Verdict::Valid => "valid",
            Verdict::Invalid => "invalid",
            Verdict::Unverified => "unverified",
        }
    }

    /// The captured service banner, when one was observed.
    pub fn banner(&self) -> Option<&str> {
        match self {
            Verdict::ServiceConfirmed { banner } => Some(banner),
            _ => None,
        }
    }
}
