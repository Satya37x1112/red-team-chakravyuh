//! The gate mints a Grant only when signature, window, technique and scope all
//! pass; every failure mode returns its typed `Denied` reason.

use ed25519_dalek::{Signer, SigningKey};
use vervet_core::attack::TechniqueId;
use vervet_scope::{Claims, Denied, Gate, Manifest, Request};

const T1046: TechniqueId = TechniqueId("T1046");

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

fn base_claims() -> Claims {
    Claims {
        engagement_id: "eng-1".into(),
        operator: "redteam".into(),
        authorized_cidrs: vec!["10.0.0.0/24".into()],
        excluded_cidrs: vec!["10.0.0.1/32".into()],
        technique_allowlist: vec!["T1046".into()],
        valid_from: 1000,
        valid_until: 2000,
    }
}

/// Sign `claims` with a fixed key; return the manifest and the authority hex.
fn signed(claims: Claims) -> (Manifest, String) {
    let sk = SigningKey::from_bytes(&[7u8; 32]);
    let sig = sk.sign(&claims.signing_bytes());
    let authority = hex(sk.verifying_key().as_bytes());
    let manifest = Manifest {
        claims,
        signature: hex(&sig.to_bytes()),
    };
    (manifest, authority)
}

fn req(last_octet: u8) -> Request {
    Request::new(format!("10.0.0.{last_octet}").parse().unwrap(), vec![445])
}

#[test]
fn authorizes_in_scope_request() {
    let (m, auth) = signed(base_claims());
    let gate = Gate::new(&auth).unwrap();
    let grant = gate.authorize(&m, T1046, req(5), 1500).unwrap();
    assert_eq!(grant.engagement_id(), "eng-1");
    assert_eq!(grant.technique(), T1046);
}

#[test]
fn rejects_tampered_claims() {
    let (mut m, auth) = signed(base_claims());
    m.claims.authorized_cidrs = vec!["0.0.0.0/0".into()];
    let gate = Gate::new(&auth).unwrap();
    assert_eq!(
        gate.authorize(&m, T1046, req(5), 1500),
        Err(Denied::BadSignature)
    );
}

#[test]
fn enforces_window_technique_and_scope() {
    let (m, auth) = signed(base_claims());
    let gate = Gate::new(&auth).unwrap();
    assert_eq!(
        gate.authorize(&m, T1046, req(5), 999),
        Err(Denied::OutsideWindow)
    );
    assert_eq!(
        gate.authorize(&m, TechniqueId("T1110"), req(5), 1500),
        Err(Denied::TechniqueNotAllowed)
    );
    assert_eq!(
        gate.authorize(&m, T1046, req(1), 1500),
        Err(Denied::TargetExcluded)
    );
    assert_eq!(
        gate.authorize(
            &m,
            T1046,
            Request::new("192.168.1.1".parse().unwrap(), vec![]),
            1500
        ),
        Err(Denied::TargetOutOfScope)
    );
}
