//! The shared backend selector for credential-access techniques.

use std::net::Ipv4Addr;

use crate::{Reachability, Verdict, Verifier};

#[cfg(feature = "ssh-auth")]
use crate::SshAuth;
#[cfg(not(feature = "ssh-auth"))]
use crate::SshProbe;

/// Ports on which a credential attempt engages the SSH backend.
pub const SSH_PORTS: &[u16] = &[22, 2022, 2222];

/// Judge one credential attempt: the SSH backend on SSH ports (real auth with
/// the `ssh-auth` feature, otherwise a service probe), a reachability check
/// elsewhere. One place owns the feature selection so techniques never repeat it.
pub fn judge(target: Ipv4Addr, port: u16, username: &str, password: &str) -> Verdict {
    if SSH_PORTS.contains(&port) {
        #[cfg(feature = "ssh-auth")]
        return SshAuth.verify(target, port, username, password);
        #[cfg(not(feature = "ssh-auth"))]
        return SshProbe.verify(target, port, username, password);
    }
    Reachability.verify(target, port, username, password)
}
