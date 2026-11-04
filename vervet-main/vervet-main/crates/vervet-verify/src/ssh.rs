//! A real, dependency-free SSH probe: the protocol version exchange.
//!
//! Per RFC 4253 an SSH server sends its identification string
//! (`SSH-2.0-<software>\r\n`) immediately on connect, before key exchange.
//! Reading that one line confirms the service and captures its banner without
//! any crypto stack. It does NOT assert credentials — that is a future backend.

use std::io::Read;
use std::net::{IpAddr, Ipv4Addr, SocketAddr, TcpStream};
use std::time::Duration;

use crate::{Verdict, Verifier};

const TIMEOUT: Duration = Duration::from_millis(600);
const MAX_BANNER: usize = 255;

/// Confirms an SSH service by its protocol banner.
pub struct SshProbe;

impl Verifier for SshProbe {
    fn verify(&self, target: Ipv4Addr, port: u16, _username: &str, _password: &str) -> Verdict {
        let addr = SocketAddr::new(IpAddr::V4(target), port);
        let Ok(mut stream) = TcpStream::connect_timeout(&addr, TIMEOUT) else {
            return Verdict::Unreachable;
        };
        let _ = stream.set_read_timeout(Some(TIMEOUT));

        let mut buf = [0u8; MAX_BANNER];
        let n = stream.read(&mut buf).unwrap_or(0);
        let text = String::from_utf8_lossy(&buf[..n]);
        let line = text.lines().next().unwrap_or("").trim();

        if line.starts_with("SSH-") {
            Verdict::ServiceConfirmed {
                banner: line.to_string(),
            }
        } else {
            Verdict::NotSsh
        }
    }
}
