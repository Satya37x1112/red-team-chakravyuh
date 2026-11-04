//! An engagement produces an audited receipt whose chain actually verifies:
//! each entry's `prev` is the blake3 handle of the previous entry.

use std::net::{Ipv4Addr, TcpListener};

use ed25519_dalek::{Signer, SigningKey};
use vervet_core::evidence::Handle;
use vervet_engage::{EngageError, run};
use vervet_scope::{Claims, Gate, Manifest, Request};
use vervet_technique::find;

use vervet_techniques as _;

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

fn fixture() -> (Manifest, String) {
    let claims = Claims {
        engagement_id: "eng-a".into(),
        operator: "redteam".into(),
        authorized_cidrs: vec!["127.0.0.1/32".into()],
        excluded_cidrs: vec![],
        technique_allowlist: vec!["T1046".into()],
        valid_from: 0,
        valid_until: u64::MAX,
    };
    let sk = SigningKey::from_bytes(&[3u8; 32]);
    let sig = sk.sign(&claims.signing_bytes());
    let manifest = Manifest {
        claims,
        signature: hex(&sig.to_bytes()),
    };
    (manifest, hex(sk.verifying_key().as_bytes()))
}

#[test]
fn receipt_audit_chain_verifies() {
    let listener = TcpListener::bind((Ipv4Addr::LOCALHOST, 0)).unwrap();
    let port = listener.local_addr().unwrap().port();

    let (manifest, authority) = fixture();
    let gate = Gate::new(&authority).unwrap();
    let technique = find("T1046").unwrap();
    let request = Request::new(Ipv4Addr::LOCALHOST, vec![port]);

    let receipt = run(&gate, &manifest, technique, request, 1).expect("authorized");

    assert_eq!(receipt.envelope.summary.attack_id, "T1046");
    assert_eq!(receipt.audit.len(), 2);
    assert_eq!(receipt.audit[0].prev, "ev:genesis");
    // The second entry chains off the first: prev == handle(first entry).
    let expected = Handle::of(&receipt.audit[0]).unwrap().as_str().to_string();
    assert_eq!(receipt.audit[1].prev, expected, "audit chain must link");
}

#[test]
fn out_of_scope_is_denied() {
    let (manifest, authority) = fixture();
    let gate = Gate::new(&authority).unwrap();
    let technique = find("T1046").unwrap();
    let request = Request::new("10.9.9.9".parse().unwrap(), vec![80]);
    let err = run(&gate, &manifest, technique, request, 1).unwrap_err();
    assert!(matches!(err, EngageError::Denied(_)));
}
