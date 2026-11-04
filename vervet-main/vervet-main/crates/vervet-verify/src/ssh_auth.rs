//! A credential-asserting SSH backend (feature `ssh-auth`).
//!
//! Performs a real SSH handshake and password authentication via libssh2,
//! returning [`Verdict::Valid`] / [`Verdict::Invalid`]. This is the heavyweight
//! tier deferred until a real SSH server could be stood up for testing
//! (testcontainers); it drops in behind [`crate::Verifier`] with no change to
//! any technique.

use std::net::{IpAddr, Ipv4Addr, SocketAddr, TcpStream};
use std::time::Duration;

use ssh2::Session;

use crate::{Verdict, Verifier};

const CONNECT_TIMEOUT: Duration = Duration::from_secs(5);
const SESSION_TIMEOUT_MS: u32 = 5000;

/// Asserts whether a username/password authenticates over SSH.
pub struct SshAuth;

impl Verifier for SshAuth {
    fn verify(&self, target: Ipv4Addr, port: u16, username: &str, password: &str) -> Verdict {
        let addr = SocketAddr::new(IpAddr::V4(target), port);
        let Ok(tcp) = TcpStream::connect_timeout(&addr, CONNECT_TIMEOUT) else {
            return Verdict::Unreachable;
        };
        let Ok(mut session) = Session::new() else {
            return Verdict::Unreachable;
        };
        session.set_timeout(SESSION_TIMEOUT_MS);
        session.set_tcp_stream(tcp);
        if session.handshake().is_err() {
            return Verdict::NotSsh;
        }
        // libssh2 returns Err on auth failure; a clean success also flips the
        // session's authenticated flag, which we confirm before claiming Valid.
        let _ = session.userauth_password(username, password);
        if session.authenticated() {
            Verdict::Valid
        } else {
            Verdict::Invalid
        }
    }
}
