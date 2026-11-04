//! T1078 checks one observation per credential pair, redacts passwords, and
//! skips cleanly when no pairs are supplied.

use std::net::{Ipv4Addr, TcpListener};

use ed25519_dalek::{Signer, SigningKey};
use vervet_core::attack::TechniqueId;
use vervet_scope::{Claims, Credential, Credentials, Gate, Manifest, Request};
use vervet_technique::find;

use vervet_techniques as _;

const T1078: TechniqueId = TechniqueId("T1078");

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

fn fixture() -> (Manifest, String) {
    let claims = Claims {
        engagement_id: "eng-va".into(),
        operator: "redteam".into(),
        authorized_cidrs: vec!["127.0.0.1/32".into()],
        excluded_cidrs: vec![],
        technique_allowlist: vec!["T1078".into()],
        valid_from: 0,
        valid_until: u64::MAX,
    };
    let sk = SigningKey::from_bytes(&[13u8; 32]);
    let sig = sk.sign(&claims.signing_bytes());
    let manifest = Manifest {
        claims,
        signature: hex(&sig.to_bytes()),
    };
    (manifest, hex(sk.verifying_key().as_bytes()))
}

fn creds(pairs: Vec<Credential>) -> Credentials {
    Credentials {
        usernames: vec![],
        password: String::new(),
        pairs,
    }
}

#[test]
fn one_check_per_pair_and_redacts_passwords() {
    let listener = TcpListener::bind((Ipv4Addr::LOCALHOST, 0)).unwrap();
    let port = listener.local_addr().unwrap().port();

    let (manifest, authority) = fixture();
    let gate = Gate::new(&authority).unwrap();
    let technique = find("T1078").expect("registered");

    let pairs = vec![
        Credential {
            username: "svc-a".into(),
            password: "topsecret-a".into(),
        },
        Credential {
            username: "svc-b".into(),
            password: "topsecret-b".into(),
        },
    ];
    let request = Request::new(Ipv4Addr::LOCALHOST, vec![port]).with_credentials(creds(pairs));
    let grant = gate.authorize(&manifest, T1078, request, 1).unwrap();

    let ev = technique.engage(&grant);
    let checks = ev
        .observations
        .iter()
        .filter(|o| o.kind == "account_check")
        .count();
    assert_eq!(checks, 2, "one observation per credential pair");
    assert!(
        ev.observations
            .iter()
            .all(|o| !o.detail.contains("topsecret")),
        "passwords must never appear in evidence"
    );
}

#[test]
fn skips_without_pairs() {
    let (manifest, authority) = fixture();
    let gate = Gate::new(&authority).unwrap();
    let technique = find("T1078").unwrap();
    let request = Request::new(Ipv4Addr::LOCALHOST, vec![22]).with_credentials(creds(vec![]));
    let grant = gate.authorize(&manifest, T1078, request, 1).unwrap();

    let ev = technique.engage(&grant);
    assert!(ev.observations.iter().any(|o| o.kind == "check_skipped"));
    assert!(ev.observations.iter().all(|o| o.kind != "account_check"));
}
