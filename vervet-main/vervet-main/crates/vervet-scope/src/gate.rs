//! The sole minter of [`Grant`]s: verifies a signed manifest and request.

use ed25519_dalek::{Signature, VerifyingKey};
use vervet_core::attack::TechniqueId;

use crate::cidr::Cidr;
use crate::grant::{Grant, Request};
use crate::manifest::Manifest;

/// Why an authorization request was refused — returned verbatim to the consumer
/// as honest, typed refusal, never a silent failure.
#[derive(Debug, PartialEq, Eq)]
pub enum Denied {
    /// The manifest signature failed to verify against the authority key.
    BadSignature,
    /// The current time falls outside the engagement window.
    OutsideWindow,
    /// The technique is absent from the manifest allowlist.
    TechniqueNotAllowed,
    /// The target lies within no authorized CIDR.
    TargetOutOfScope,
    /// The target falls within an excluded CIDR.
    TargetExcluded,
    /// The authority key or signature could not be decoded.
    MalformedKey,
}

impl std::fmt::Display for Denied {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(match self {
            Denied::BadSignature => "manifest signature failed verification",
            Denied::OutsideWindow => "current time is outside the engagement window",
            Denied::TechniqueNotAllowed => "technique is not in the manifest allowlist",
            Denied::TargetOutOfScope => "target is not within any authorized CIDR",
            Denied::TargetExcluded => "target falls within an excluded CIDR",
            Denied::MalformedKey => "authority key or signature was malformed",
        })
    }
}

impl std::error::Error for Denied {}

/// The sole minter of [`Grant`]s. Holds the trusted authority key the manifest
/// signature is checked against — supplied out-of-band, never from the manifest
/// itself (a self-signed manifest would be forgeable).
pub struct Gate {
    authority: VerifyingKey,
}

impl Gate {
    /// Build a gate from a hex-encoded 32-byte Ed25519 public key.
    pub fn new(authority_hex: &str) -> Result<Gate, Denied> {
        let bytes = decode_hex::<32>(authority_hex).ok_or(Denied::MalformedKey)?;
        let authority = VerifyingKey::from_bytes(&bytes).map_err(|_| Denied::MalformedKey)?;
        Ok(Gate { authority })
    }

    /// Verify the manifest and request, minting a [`Grant`] only if every check
    /// passes. `now` is unix seconds, injected so the check stays testable and
    /// the only wall-clock read lives at the CLI boundary.
    pub fn authorize(
        &self,
        manifest: &Manifest,
        technique: TechniqueId,
        request: Request,
        now: u64,
    ) -> Result<Grant, Denied> {
        self.verify_signature(manifest)?;
        let c = &manifest.claims;
        if now < c.valid_from || now > c.valid_until {
            return Err(Denied::OutsideWindow);
        }
        if !c
            .technique_allowlist
            .iter()
            .any(|t| t == technique.as_str())
        {
            return Err(Denied::TechniqueNotAllowed);
        }
        if in_any(&c.excluded_cidrs, request.target) {
            return Err(Denied::TargetExcluded);
        }
        if !in_any(&c.authorized_cidrs, request.target) {
            return Err(Denied::TargetOutOfScope);
        }
        Ok(Grant::new(request, c.engagement_id.clone(), technique))
    }

    fn verify_signature(&self, manifest: &Manifest) -> Result<(), Denied> {
        let sig_bytes = decode_hex::<64>(&manifest.signature).ok_or(Denied::MalformedKey)?;
        let sig = Signature::from_bytes(&sig_bytes);
        self.authority
            .verify_strict(&manifest.claims.signing_bytes(), &sig)
            .map_err(|_| Denied::BadSignature)
    }
}

/// Whether `ip` falls in any parseable CIDR in `blocks`.
fn in_any(blocks: &[String], ip: std::net::Ipv4Addr) -> bool {
    blocks
        .iter()
        .filter_map(|s| Cidr::parse(s))
        .any(|n| n.contains(ip))
}

/// Decode exactly `N` bytes of hex, or `None`.
fn decode_hex<const N: usize>(s: &str) -> Option<[u8; N]> {
    if s.len() != N * 2 {
        return None;
    }
    let mut out = [0u8; N];
    for (i, byte) in out.iter_mut().enumerate() {
        *byte = u8::from_str_radix(&s[i * 2..i * 2 + 2], 16).ok()?;
    }
    Some(out)
}
