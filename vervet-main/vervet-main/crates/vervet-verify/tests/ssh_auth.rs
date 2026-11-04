//! End-to-end: the credential-asserting SSH backend against a real sshd in a
//! container. Gated behind `ssh-auth` so the default test suite needs no Docker.
//!
//! Run with: `cargo test -p vervet-verify --features ssh-auth`

#![cfg(feature = "ssh-auth")]

use std::net::Ipv4Addr;
use std::thread::sleep;
use std::time::Duration;

use testcontainers::GenericImage;
use testcontainers::clients::Cli;
use vervet_verify::{SshAuth, Verdict, Verifier};

const USER: &str = "vervet";
const PASS: &str = "s3cr3t-vervet";

/// A throwaway OpenSSH server with password auth and a known account.
fn openssh() -> GenericImage {
    GenericImage::new("lscr.io/linuxserver/openssh-server", "latest")
        .with_env_var("PUID", "1000")
        .with_env_var("PGID", "1000")
        .with_env_var("PASSWORD_ACCESS", "true")
        .with_env_var("USER_NAME", USER)
        .with_env_var("USER_PASSWORD", PASS)
        .with_exposed_port(2222)
}

/// Poll the backend until the container's sshd accepts the known account, so
/// the test never depends on a brittle log-line match. Only `Valid` ends the
/// wait — an early `Invalid` may just mean user setup has not finished yet.
fn await_valid(port: u16) -> Verdict {
    let mut last = Verdict::Unreachable;
    for _ in 0..60 {
        last = SshAuth.verify(Ipv4Addr::LOCALHOST, port, USER, PASS);
        if last == Verdict::Valid {
            return last;
        }
        sleep(Duration::from_secs(1));
    }
    last
}

#[test]
fn asserts_valid_and_invalid_credentials() {
    let docker = Cli::default();
    let node = docker.run(openssh());
    let port = node.get_host_port_ipv4(2222);

    assert_eq!(
        await_valid(port),
        Verdict::Valid,
        "the correct password must authenticate"
    );

    let bad = SshAuth.verify(Ipv4Addr::LOCALHOST, port, USER, "wrong-password");
    assert_eq!(bad, Verdict::Invalid, "a wrong password must be rejected");
}
