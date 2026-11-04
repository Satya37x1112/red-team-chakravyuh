//! The SSH probe confirms a service from its real protocol banner, flags
//! non-SSH services, and reports unreachable endpoints honestly.

use std::io::Write;
use std::net::{Ipv4Addr, TcpListener};

use vervet_verify::{SshProbe, Verdict, Verifier};

/// Accept one connection on loopback and write `payload`, returning the port.
fn serve_once(payload: &'static [u8]) -> u16 {
    let listener = TcpListener::bind((Ipv4Addr::LOCALHOST, 0)).unwrap();
    let port = listener.local_addr().unwrap().port();
    std::thread::spawn(move || {
        if let Ok((mut sock, _)) = listener.accept() {
            let _ = sock.write_all(payload);
        }
    });
    port
}

#[test]
fn confirms_ssh_from_banner() {
    let port = serve_once(b"SSH-2.0-OpenSSH_9.6p1 Ubuntu-3\r\n");
    let v = SshProbe.verify(Ipv4Addr::LOCALHOST, port, "alice", "pw");
    assert_eq!(v.kind(), "ssh_confirmed");
    assert_eq!(v.banner(), Some("SSH-2.0-OpenSSH_9.6p1 Ubuntu-3"));
}

#[test]
fn flags_non_ssh_service() {
    let port = serve_once(b"220 smtp.example.com ESMTP\r\n");
    let v = SshProbe.verify(Ipv4Addr::LOCALHOST, port, "alice", "pw");
    assert_eq!(v, Verdict::NotSsh);
}

#[test]
fn unreachable_when_nothing_listens() {
    let listener = TcpListener::bind((Ipv4Addr::LOCALHOST, 0)).unwrap();
    let port = listener.local_addr().unwrap().port();
    drop(listener); // free the port so the connect is refused
    let v = SshProbe.verify(Ipv4Addr::LOCALHOST, port, "alice", "pw");
    assert_eq!(v, Verdict::Unreachable);
}
