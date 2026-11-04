//! Shared black-box helpers for the CLI integration tests. Each test binary
//! that does `mod common;` pulls in only the subset it uses, so unused helpers
//! are expected here.
#![allow(dead_code)]

use std::path::Path;
use std::process::Command;

use ed25519_dalek::{Signer, SigningKey};
use serde_json::json;

/// Run the real `vervet` binary, returning (stdout, stderr, exit code).
pub fn vervet(args: &[&str]) -> (String, String, i32) {
    let out = Command::new(env!("CARGO_BIN_EXE_vervet"))
        .args(args)
        .output()
        .expect("spawn vervet");
    (
        String::from_utf8_lossy(&out.stdout).into_owned(),
        String::from_utf8_lossy(&out.stderr).into_owned(),
        out.status.code().unwrap_or(-1),
    )
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

/// Sign a manifest scoping loopback for `techniques`, write it to
/// `dir/manifest.json`, and return the authority key the binary verifies with.
pub fn write_manifest(dir: &Path, engagement: &str, techniques: &[&str]) -> String {
    let sk = SigningKey::from_bytes(&[5u8; 32]);
    let claims = json!({
        "engagement_id": engagement,
        "operator": "cli-test",
        "authorized_cidrs": ["127.0.0.1/32"],
        "excluded_cidrs": [],
        "technique_allowlist": techniques,
        "valid_from": 0,
        "valid_until": u64::MAX,
    });
    let typed: vervet_scope::Claims = serde_json::from_value(claims.clone()).unwrap();
    let sig = sk.sign(&typed.signing_bytes());
    let manifest = json!({ "claims": claims, "signature": hex(&sig.to_bytes()) });
    std::fs::write(
        dir.join("manifest.json"),
        serde_json::to_vec(&manifest).unwrap(),
    )
    .unwrap();
    hex(sk.verifying_key().as_bytes())
}
