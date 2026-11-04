//! The signed authorization document for an engagement.

use serde::{Deserialize, Serialize};

/// A signed engagement authorization. `claims` is the signed payload;
/// `signature` is an Ed25519 signature over the canonical JSON of `claims`.
#[derive(Clone, Debug, Deserialize)]
pub struct Manifest {
    /// The signed payload: scope, window, and allowlist.
    pub claims: Claims,
    /// Hex-encoded 64-byte Ed25519 signature over the canonical claims JSON.
    pub signature: String,
}

/// The signed body of a manifest. Field order is the canonical signing order.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Claims {
    /// Identifier for the engagement this manifest authorizes.
    pub engagement_id: String,
    /// The operator the authority cleared to run it.
    pub operator: String,
    /// IPv4 CIDRs the operator may act against, e.g. `10.0.0.0/24`.
    pub authorized_cidrs: Vec<String>,
    /// CIDRs explicitly carved out, checked before authorization.
    #[serde(default)]
    pub excluded_cidrs: Vec<String>,
    /// ATT&CK technique ids the operator is cleared to fire.
    pub technique_allowlist: Vec<String>,
    /// Engagement window lower bound, unix seconds (inclusive).
    pub valid_from: u64,
    /// Engagement window upper bound, unix seconds (inclusive).
    pub valid_until: u64,
}

impl Claims {
    /// Canonical bytes the signature is computed over. Struct field order is
    /// stable, so `to_vec` is canonical here.
    pub fn signing_bytes(&self) -> Vec<u8> {
        serde_json::to_vec(self).expect("claims serialize")
    }
}
