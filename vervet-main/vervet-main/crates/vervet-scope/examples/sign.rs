//! Dev helper: sign a scope manifest with a seeded Ed25519 key.
//!
//! Usage: cargo run -p vervet-scope --example sign -- <seed-hex-32b> <claims.json>
//! Prints the authority public key to stderr and the signed manifest to stdout.

use ed25519_dalek::{Signer, SigningKey};
use vervet_scope::Claims;

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let (Some(seed_hex), Some(claims_path)) = (args.first(), args.get(1)) else {
        eprintln!("usage: sign <seed-hex-32-bytes> <claims.json>");
        std::process::exit(1);
    };
    let seed = decode32(seed_hex).expect("seed must be 64 hex chars");
    let sk = SigningKey::from_bytes(&seed);

    let text = std::fs::read_to_string(claims_path).expect("read claims");
    let claims: Claims = serde_json::from_str(&text).expect("parse claims");
    let sig = sk.sign(&claims.signing_bytes());

    eprintln!("authority: {}", hex(sk.verifying_key().as_bytes()));
    let manifest = serde_json::json!({
        "claims": claims,
        "signature": hex(&sig.to_bytes()),
    });
    println!("{}", serde_json::to_string_pretty(&manifest).unwrap());
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

fn decode32(s: &str) -> Option<[u8; 32]> {
    if s.len() != 64 {
        return None;
    }
    let mut out = [0u8; 32];
    for (i, b) in out.iter_mut().enumerate() {
        *b = u8::from_str_radix(&s[i * 2..i * 2 + 2], 16).ok()?;
    }
    Some(out)
}
