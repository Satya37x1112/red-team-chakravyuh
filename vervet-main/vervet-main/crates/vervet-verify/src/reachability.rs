//! The default backend: confirm the service port is reachable, nothing more.

use std::net::{IpAddr, Ipv4Addr, SocketAddr, TcpStream};
use std::time::Duration;

use crate::{Verdict, Verifier};

const TIMEOUT: Duration = Duration::from_millis(400);

/// Establishes a TCP connection and reports reachability only — it never claims
/// a credential outcome it did not measure.
pub struct Reachability;

impl Verifier for Reachability {
    fn verify(&self, target: Ipv4Addr, port: u16, _username: &str, _password: &str) -> Verdict {
        let addr = SocketAddr::new(IpAddr::V4(target), port);
        if TcpStream::connect_timeout(&addr, TIMEOUT).is_ok() {
            Verdict::Unverified
        } else {
            Verdict::Unreachable
        }
    }
}
