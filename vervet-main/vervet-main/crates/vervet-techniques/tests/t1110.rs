//! T1110.003 makes at most one attempt per unique account, redacts the sprayed
//! password, and cleanly skips when no credentials are supplied.

use std::net::{Ipv4Addr, TcpListener};

use ed25519_dalek::{Signer, SigningKey};
use vervet_core::attack::TechniqueId;
use vervet_scope::{Claims, Credentials, Gate, Manifest, Request};
use vervet_technique::find;

use vervet_techniques as _;

const T1110: TechniqueId = TechniqueId("T1110.003");

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

fn fixture() -> (Manifest, String) {
    let claims = Claims {
        engagement_id: "eng-spray".into(),
        operator: "redteam".into(),
        authorized_cidrs: vec!["127.0.0.1/32".into()],
        excluded_cidrs: vec![],
        technique_allowlist: vec!["T1110.003".into()],
        valid_from: 0,
        valid_until: u64::MAX,
    };
    let sk = SigningKey::from_bytes(&[5u8; 32]);
    let sig = sk.sign(&claims.signing_bytes());
    let manifest = Manifest {
        claims,
        signature: hex(&sig.to_bytes()),
    };
    (manifest, hex(sk.verifying_key().as_bytes()))
}

#[test]
fn one_attempt_per_unique_account_and_redacts_password() {
    let listener = TcpListener::bind((Ipv4Addr::LOCALHOST, 0)).unwrap();
    let port = listener.local_addr().unwrap().port();

    let (manifest, authority) = fixture();
    let gate = Gate::new(&authority).unwrap();
    let technique = find("T1110.003").expect("registered");

    let creds = Credentials {
        usernames: vec!["alice".into(), "bob".into(), "alice".into()],
        password: "Spring2025!".into(),
        pairs: vec![],
    };
    let request = Request::new(Ipv4Addr::LOCALHOST, vec![port]).with_credentials(creds);
    let grant = gate.authorize(&manifest, T1110, request, 1).unwrap();

    let ev = technique.engage(&grant);
    let attempts = ev
        .observations
        .iter()
        .filter(|o| o.kind == "auth_attempt")
        .count();
    assert_eq!(attempts, 2, "duplicate account must not be sprayed twice");
    assert!(
        ev.observations
            .iter()
            .all(|o| !o.detail.contains("Spring2025")),
        "the sprayed password must never appear in evidence"
    );
}

#[test]
fn skips_cleanly_without_credentials() {
    let (manifest, authority) = fixture();
    let gate = Gate::new(&authority).unwrap();
    let technique = find("T1110.003").unwrap();

    let request = Request::new(Ipv4Addr::LOCALHOST, vec![445]);
    let grant = gate.authorize(&manifest, T1110, request, 1).unwrap();

    let ev = technique.engage(&grant);
    assert!(ev.observations.iter().any(|o| o.kind == "spray_skipped"));
    assert!(ev.observations.iter().all(|o| o.kind != "auth_attempt"));
}
