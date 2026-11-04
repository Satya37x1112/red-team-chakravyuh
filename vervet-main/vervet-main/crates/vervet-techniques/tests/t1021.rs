//! T1021 reports one observation per probed service, reachable or not.

use std::net::{Ipv4Addr, TcpListener};

use ed25519_dalek::{Signer, SigningKey};
use vervet_core::attack::TechniqueId;
use vervet_scope::{Claims, Gate, Manifest, Request};
use vervet_technique::find;

use vervet_techniques as _;

const T1021: TechniqueId = TechniqueId("T1021");

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

fn fixture() -> (Manifest, String) {
    let claims = Claims {
        engagement_id: "eng-lat".into(),
        operator: "redteam".into(),
        authorized_cidrs: vec!["127.0.0.1/32".into()],
        excluded_cidrs: vec![],
        technique_allowlist: vec!["T1021".into()],
        valid_from: 0,
        valid_until: u64::MAX,
    };
    let sk = SigningKey::from_bytes(&[11u8; 32]);
    let sig = sk.sign(&claims.signing_bytes());
    let manifest = Manifest {
        claims,
        signature: hex(&sig.to_bytes()),
    };
    (manifest, hex(sk.verifying_key().as_bytes()))
}

#[test]
fn reports_open_and_closed_services() {
    // One open port (a live listener) and one closed (bound then freed).
    let open = TcpListener::bind((Ipv4Addr::LOCALHOST, 0)).unwrap();
    let open_port = open.local_addr().unwrap().port();
    let closed = TcpListener::bind((Ipv4Addr::LOCALHOST, 0)).unwrap();
    let closed_port = closed.local_addr().unwrap().port();
    drop(closed);

    let (manifest, authority) = fixture();
    let gate = Gate::new(&authority).unwrap();
    let technique = find("T1021").expect("registered");
    let request = Request::new(Ipv4Addr::LOCALHOST, vec![open_port, closed_port]);
    let grant = gate.authorize(&manifest, T1021, request, 1).unwrap();

    let ev = technique.engage(&grant);
    let services: Vec<&str> = ev
        .observations
        .iter()
        .filter(|o| o.kind == "remote_service")
        .map(|o| o.detail.as_str())
        .collect();

    assert_eq!(services.len(), 2, "one observation per probed service");
    assert!(services.iter().any(|d| d.contains("verdict=unverified")));
    assert!(services.iter().any(|d| d.contains("verdict=unreachable")));
}
