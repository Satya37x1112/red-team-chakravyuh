#![deny(missing_docs)]

//! The auth-verifier seam. A [`Verifier`] judges one authentication attempt
//! against a service and returns a [`Verdict`]. v0 ships protocol-level probes
//! (no heavyweight SSH stack): they confirm *what* is listening, not yet
//! *whether* the credentials are valid. A credential-asserting backend that
//! returns [`Verdict::Valid`] / [`Verdict::Invalid`] drops in behind this same
//! trait without touching any technique.

pub mod judge;
pub mod reachability;
pub mod ssh;
pub mod verdict;

#[cfg(feature = "ssh-auth")]
pub mod ssh_auth;

pub use judge::judge;
pub use reachability::Reachability;
pub use ssh::SshProbe;
pub use verdict::Verdict;

#[cfg(feature = "ssh-auth")]
pub use ssh_auth::SshAuth;

use std::net::Ipv4Addr;

/// A backend that judges an authentication attempt against a service endpoint.
/// `username`/`password` are accepted by every backend so a credential-asserting
/// verifier is a drop-in; probe backends ignore them.
pub trait Verifier {
    /// Judge one attempt against `target:port` and return a [`Verdict`].
    fn verify(&self, target: Ipv4Addr, port: u16, username: &str, password: &str) -> Verdict;
}
