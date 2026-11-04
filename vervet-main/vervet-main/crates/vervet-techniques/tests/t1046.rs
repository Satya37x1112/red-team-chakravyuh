//! End-to-end: a signed manifest authorizes T1046 against loopback, the gate
//! mints a grant, and the technique observes a port we actually opened.

use std::net::{Ipv4Addr, TcpListener};

use ed25519_dalek::{Signer, SigningKey};
use vervet_core::attack::TechniqueId;
use vervet_scope::{Claims, Gate, Manifest, Request};
use vervet_technique::find;

// Force-link the crate under test so its `inventory::submit!` entries register.
use vervet_techniques as _;

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

fn signed(claims: Claims) -> (Manifest, String) {
    let sk = SigningKey::from_bytes(&[9u8; 32]);
    let sig = sk.sign(&claims.signing_bytes());
    let manifest = Manifest {
        claims,
        signature: hex(&sig.to_bytes()),
    };
    (manifest, hex(sk.verifying_key().as_bytes()))
}

#[test]
fn discovers_an_open_loopback_port() {
    // Open a real port on loopback so the connect-scan has something to find.
    let listener = TcpListener::bind((Ipv4Addr::LOCALHOST, 0)).unwrap();
    let port = listener.local_addr().unwrap().port();

    let claims = Claims {
        engagement_id: "eng-loop".into(),
        operator: "redteam".into(),
        authorized_cidrs: vec!["127.0.0.1/32".into()],
        excluded_cidrs: vec![],
        technique_allowlist: vec!["T1046".into()],
        valid_from: 0,
        valid_until: u64::MAX,
    };
    let (manifest, authority) = signed(claims);
    let gate = Gate::new(&authority).unwrap();

    let request = Request::new(Ipv4Addr::LOCALHOST, vec![port]);
    let technique = find("T1046").expect("T1046 registered");
    let grant = gate
        .authorize(&manifest, TechniqueId("T1046"), request, 1)
        .expect("authorized");

    let evidence = technique.engage(&grant);
    assert!(
        evidence
            .observations
            .iter()
            .any(|o| o.kind == "port_open" && o.detail == format!("tcp/{port}")),
        "expected the open loopback port to be observed"
    );
}
