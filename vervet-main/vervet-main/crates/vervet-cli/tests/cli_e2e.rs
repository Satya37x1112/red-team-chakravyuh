//! Black-box end-to-end: drive the REAL `vervet` binary against a live sshd in
//! a container. This exercises the whole CLI surface an AI orchestrator uses —
//! manifest loading, the gate, dispatch, real credential verification, the
//! receipt on stdout, the run store, and `report` aggregation — end to end.
//!
//! Gated behind `ssh-auth` (needs Docker): `cargo test -p vervet-cli --features ssh-auth`.

#![cfg(feature = "ssh-auth")]

use std::path::Path;
use std::process::Command;
use std::thread::sleep;
use std::time::Duration;

use ed25519_dalek::{Signer, SigningKey};
use serde_json::{Value, json};
use testcontainers::clients::Cli;
use testcontainers::{GenericImage, RunnableImage};

const USER: &str = "vervet";
const PASS: &str = "s3cr3t-vervet";
// A distinct SSH port from the library pipeline test (2222), so the two e2e
// suites never contend for the same host port if run together.
const PORT: u16 = 2022;
const ENGAGEMENT: &str = "cli-e2e";

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

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

/// Sign a manifest authorizing the spray against loopback and write it to
/// `dir/manifest.json`, returning the authority key the binary verifies against.
fn write_manifest(dir: &Path) -> String {
    let sk = SigningKey::from_bytes(&[9u8; 32]);
    let claims = json!({
        "engagement_id": ENGAGEMENT,
        "operator": "e2e",
        "authorized_cidrs": ["127.0.0.1/32"],
        "excluded_cidrs": [],
        "technique_allowlist": ["T1110.003"],
        "valid_from": 0,
        "valid_until": u64::MAX,
    });
    // The signature covers the canonical claims bytes; mirror serde's field order
    // by signing the exact bytes the binary will reconstruct from these claims.
    let claims_typed: vervet_scope::Claims = serde_json::from_value(claims.clone()).unwrap();
    let sig = sk.sign(&claims_typed.signing_bytes());
    let manifest = json!({ "claims": claims, "signature": hex(&sig.to_bytes()) });
    std::fs::write(
        dir.join("manifest.json"),
        serde_json::to_vec_pretty(&manifest).unwrap(),
    )
    .unwrap();
    hex(sk.verifying_key().as_bytes())
}

/// Run the real `vervet` binary, returning (stdout, stderr, exit code).
fn vervet(args: &[&str]) -> (String, String, i32) {
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

/// The `detail` of the receipt observation whose attempt names `user`.
fn detail_for<'a>(receipt: &'a Value, user: &str) -> Option<&'a str> {
    receipt["envelope"]["handles"]
        .as_object()?
        .values()
        .filter_map(|o| o["detail"].as_str())
        .find(|d| d.contains(&format!("user={user} ")))
}

#[test]
fn cli_emulate_store_and_report_against_real_sshd() {
    let docker = Cli::default();
    let _node = docker.run(sshd());

    let dir = std::env::temp_dir().join(format!("vervet-cli-e2e-{}", std::process::id()));
    let store = dir.join("store");
    std::fs::create_dir_all(&store).unwrap();
    let authority = write_manifest(&dir);
    let manifest = dir.join("manifest.json");
    let (manifest, store) = (manifest.to_str().unwrap(), store.to_str().unwrap());

    let emulate = [
        "emulate",
        "T1110.003",
        "--manifest",
        manifest,
        "--authority",
        &authority,
        "--target",
        "127.0.0.1",
        "--ports",
        "2022",
        "--users",
        "vervet,root",
        "--password",
        PASS,
        "--store",
        store,
    ];

    // Retry the real engagement until the container's sshd is up and accepts the
    // known account — black-box readiness, no peeking at container internals.
    let mut receipt = Value::Null;
    let mut ready = false;
    for _ in 0..90 {
        let (stdout, _, code) = vervet(&emulate);
        if code == 0
            && let Ok(r) = serde_json::from_str::<Value>(&stdout)
            && detail_for(&r, USER).is_some_and(|d| d.contains("verdict=valid"))
        {
            receipt = r;
            ready = true;
            break;
        }
        sleep(Duration::from_secs(1));
    }
    assert!(ready, "sshd never accepted the known account in time");

    // The receipt carries true verdicts, and never the password.
    assert_eq!(receipt["envelope"]["summary"]["attack_id"], "T1110.003");
    assert!(
        detail_for(&receipt, USER)
            .unwrap()
            .contains("verdict=valid")
    );
    assert!(
        detail_for(&receipt, "root")
            .unwrap()
            .contains("verdict=invalid")
    );
    assert!(
        !serde_json::to_string(&receipt).unwrap().contains(PASS),
        "password must never appear in the receipt"
    );

    // Out-of-scope target: a hard, typed refusal with exit code 2.
    let deny = [
        "emulate",
        "T1110.003",
        "--manifest",
        manifest,
        "--authority",
        &authority,
        "--target",
        "10.0.0.1",
        "--ports",
        "2022",
        "--users",
        "vervet",
        "--password",
        PASS,
    ];
    let (_, stderr, code) = vervet(&deny);
    assert_eq!(code, 2, "out-of-scope must exit 2");
    assert!(stderr.contains("denied"), "denial is explicit: {stderr}");

    // `report` folds the stored receipt into a coverage map with no file-piping.
    let (stdout, _, code) = vervet(&["report", "--store", store, "--engagement", ENGAGEMENT]);
    assert_eq!(code, 0);
    let cov: Value = serde_json::from_str(&stdout).unwrap();
    let cred = &cov["tactics"]["credential_access"];
    assert!(
        cred.as_array().unwrap().iter().any(|t| t == "T1110.003"),
        "coverage maps the spray under credential_access: {cov}"
    );

    let _ = std::fs::remove_dir_all(&dir);
}
