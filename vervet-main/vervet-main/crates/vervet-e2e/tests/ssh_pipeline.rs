//! Full-stack end-to-end: the canonical `authorize → engage → emit` pipeline
//! (`vervet_engage::run`) driven against a REAL sshd in a container, with the
//! credential-asserting backend live. This proves the whole spine works against
//! a real service — the gate mints a grant, the technique authenticates for
//! real, and the receipt carries true `valid`/`invalid` verdicts with passwords
//! redacted and an audit chain that links.
//!
//! Gated behind `ssh-auth` (needs Docker): `cargo test -p vervet-e2e --features ssh-auth`.

#![cfg(feature = "ssh-auth")]

use std::net::Ipv4Addr;
use std::thread::sleep;
use std::time::Duration;

use ed25519_dalek::{Signer, SigningKey};
use serde_json::Value;
use testcontainers::clients::Cli;
use testcontainers::{GenericImage, RunnableImage};

use vervet_core::evidence::Handle;
use vervet_engage::{EngageError, Receipt, run};
use vervet_scope::{Claims, Credential, Credentials, Gate, Manifest, Request};
use vervet_technique::find;
use vervet_verify::{Verdict, judge};

use vervet_techniques as _;

const USER: &str = "vervet";
const PASS: &str = "s3cr3t-vervet";
// Pin the host port to an SSH port so `judge` engages the SSH backend — a
// dynamic high port would silently fall through to a reachability probe.
const PORT: u16 = 2222;

/// A throwaway OpenSSH server with a known password account, pinned to PORT.
fn sshd() -> RunnableImage<GenericImage> {
    let image = GenericImage::new("lscr.io/linuxserver/openssh-server", "latest")
        .with_env_var("PUID", "1000")
        .with_env_var("PGID", "1000")
        .with_env_var("PASSWORD_ACCESS", "true")
        .with_env_var("USER_NAME", USER)
        .with_env_var("USER_PASSWORD", PASS)
        .with_exposed_port(2222);
    RunnableImage::from(image).with_mapped_port((PORT, 2222))
}

/// Block until the container's sshd accepts the known account, so the test
/// never races container startup. Only `Valid` ends the wait.
fn await_ready() {
    for _ in 0..90 {
        if judge(Ipv4Addr::LOCALHOST, PORT, USER, PASS) == Verdict::Valid {
            return;
        }
        sleep(Duration::from_secs(1));
    }
    panic!("sshd never accepted the known account within the timeout");
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

/// Sign a manifest authorizing `techniques` against loopback, returning it with
/// the authority public key the gate verifies against.
fn manifest(engagement: &str, cidr: &str, techniques: &[&str]) -> (Manifest, String) {
    let claims = Claims {
        engagement_id: engagement.into(),
        operator: "e2e".into(),
        authorized_cidrs: vec![cidr.into()],
        excluded_cidrs: vec![],
        technique_allowlist: techniques.iter().map(|t| t.to_string()).collect(),
        valid_from: 0,
        valid_until: u64::MAX,
    };
    let sk = SigningKey::from_bytes(&[7u8; 32]);
    let sig = sk.sign(&claims.signing_bytes());
    let m = Manifest {
        claims,
        signature: hex(&sig.to_bytes()),
    };
    (m, hex(sk.verifying_key().as_bytes()))
}

/// The `detail` of the observation whose attempt names `user`, if any.
fn detail_for<'a>(json: &'a Value, user: &str) -> Option<&'a str> {
    json["envelope"]["handles"]
        .as_object()?
        .values()
        .filter_map(|o| o["detail"].as_str())
        .find(|d| d.contains(&format!("user={user} ")))
}

/// Every audit entry chains off the previous one's blake3 handle.
fn audit_chain_links(receipt: &Receipt) {
    assert_eq!(receipt.audit.len(), 2, "authorize + engage");
    assert_eq!(receipt.audit[0].prev, "ev:genesis");
    let expected = Handle::of(&receipt.audit[0]).unwrap().as_str().to_string();
    assert_eq!(receipt.audit[1].prev, expected, "audit chain must link");
}

#[test]
fn full_pipeline_asserts_real_credentials() {
    let docker = Cli::default();
    let node = docker.run(sshd());
    assert_eq!(node.get_host_port_ipv4(2222), PORT, "host port is pinned");
    await_ready();

    let target = Ipv4Addr::LOCALHOST;

    // --- T1110.003 password spray: one password across distinct accounts. ---
    let (m, authority) = manifest("e2e-spray", "127.0.0.1/32", &["T1110.003"]);
    let gate = Gate::new(&authority).unwrap();
    let creds = Credentials {
        usernames: vec![USER.into(), "root".into(), "nobody".into()],
        password: PASS.into(),
        pairs: vec![],
    };
    let req = Request::new(target, vec![PORT]).with_credentials(creds);
    let spray = run(&gate, &m, find("T1110.003").unwrap(), req, 1).expect("authorized");

    assert_eq!(spray.envelope.summary.attack_id, "T1110.003");
    assert_eq!(spray.envelope.summary.tactic, "credential_access");
    assert_eq!(
        spray.envelope.summary.observation_count, 3,
        "one per account"
    );
    let sv = serde_json::to_value(&spray).unwrap();
    assert!(detail_for(&sv, USER).unwrap().contains("verdict=valid"));
    assert!(detail_for(&sv, "root").unwrap().contains("verdict=invalid"));
    assert!(
        detail_for(&sv, "nobody")
            .unwrap()
            .contains("verdict=invalid")
    );
    audit_chain_links(&spray);

    // --- T1078 valid accounts: per-account password validation. ---
    let (m, authority) = manifest("e2e-va", "127.0.0.1/32", &["T1078"]);
    let gate = Gate::new(&authority).unwrap();
    let pairs = vec![
        Credential {
            username: USER.into(),
            password: PASS.into(),
        },
        Credential {
            username: "ghost".into(),
            password: "no-such-account".into(),
        },
    ];
    let creds = Credentials {
        usernames: vec![],
        password: String::new(),
        pairs,
    };
    let req = Request::new(target, vec![PORT]).with_credentials(creds);
    let va = run(&gate, &m, find("T1078").unwrap(), req, 1).expect("authorized");

    assert_eq!(va.envelope.summary.attack_id, "T1078");
    assert_eq!(va.envelope.summary.tactic, "initial_access");
    let vv = serde_json::to_value(&va).unwrap();
    assert!(detail_for(&vv, USER).unwrap().contains("verdict=valid"));
    assert!(
        detail_for(&vv, "ghost")
            .unwrap()
            .contains("verdict=invalid")
    );
    audit_chain_links(&va);

    // --- The password never reaches evidence, on any verdict. ---
    let blob = serde_json::to_string(&spray).unwrap() + &serde_json::to_string(&va).unwrap();
    assert!(
        !blob.contains(PASS),
        "password must never appear in a receipt"
    );
}

#[test]
fn gate_denies_a_target_out_of_scope() {
    // The manifest scopes a different network; the gate must refuse loopback
    // BEFORE any engagement — authorization precedes contact with the service.
    let (m, authority) = manifest("e2e-deny", "10.0.0.0/8", &["T1110.003"]);
    let gate = Gate::new(&authority).unwrap();
    let creds = Credentials {
        usernames: vec![USER.into()],
        password: PASS.into(),
        pairs: vec![],
    };
    let req = Request::new(Ipv4Addr::LOCALHOST, vec![PORT]).with_credentials(creds);
    let err = run(&gate, &m, find("T1110.003").unwrap(), req, 1).unwrap_err();
    assert!(
        matches!(err, EngageError::Denied(_)),
        "out-of-scope is denied"
    );
}
