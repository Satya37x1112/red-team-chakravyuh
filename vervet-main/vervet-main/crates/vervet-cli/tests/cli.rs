//! The CLI is the contract, so the verb surface is tested as a black box
//! through the compiled binary — no Docker, no live services. T1046 probes a
//! loopback listener we bind ourselves, so the emulate → explain → report flow
//! is fully deterministic.

mod common;

use std::net::TcpListener;

use common::{vervet, write_manifest};
use serde_json::Value;

#[test]
fn verb_surface_is_well_behaved() {
    // describe — the machine-readable bootstrap contract.
    let (out, _, code) = vervet(&["describe"]);
    assert_eq!(code, 0);
    let d: Value = serde_json::from_str(&out).expect("describe emits JSON");
    assert_eq!(d["protocol"]["schema"], "vq1");
    assert!(
        d["techniques"]
            .as_array()
            .unwrap()
            .iter()
            .any(|t| t["id"] == "T1046"),
        "describe lists registered techniques"
    );

    // schema — the receipt contract.
    let (out, _, code) = vervet(&["schema"]);
    assert_eq!(code, 0);
    let s: Value = serde_json::from_str(&out).expect("schema emits JSON");
    assert!(s["$id"].as_str().unwrap().contains("vq1-receipt"));

    // help / version on stdout, exit 0.
    let (out, _, code) = vervet(&["help"]);
    assert_eq!(code, 0);
    assert!(out.contains("USAGE"));
    assert_eq!(vervet(&["--help"]).2, 0);
    assert!(vervet(&["--version"]).0.contains("vervet 0.1.0"));
    assert!(vervet(&["-V"]).0.contains("vervet 0.1.0"));

    // unknown verb — exit 1, pointed at help.
    let (_, err, code) = vervet(&["frobnicate"]);
    assert_eq!(code, 1);
    assert!(err.contains("unknown verb"));
}

#[test]
fn emulate_explain_report_and_denial() {
    // A loopback listener guarantees exactly one open port for T1046 to find.
    let listener = TcpListener::bind(("127.0.0.1", 0)).unwrap();
    let port = listener.local_addr().unwrap().port().to_string();

    let dir = std::env::temp_dir().join(format!("vervet-cli-{}", std::process::id()));
    let store = dir.join("store");
    std::fs::create_dir_all(&store).unwrap();
    let authority = write_manifest(&dir, "cli-eng", &["T1046"]);
    let manifest = dir.join("manifest.json");
    let receipt_path = dir.join("receipt.json");
    let (manifest, store) = (manifest.to_str().unwrap(), store.to_str().unwrap());

    // emulate — authorize and fire against the in-scope listener.
    let (out, _, code) = vervet(&[
        "emulate",
        "T1046",
        "--manifest",
        manifest,
        "--authority",
        &authority,
        "--target",
        "127.0.0.1",
        "--ports",
        &port,
        "--store",
        store,
    ]);
    assert_eq!(code, 0, "in-scope engagement succeeds");
    let receipt: Value = serde_json::from_str(&out).unwrap();
    assert_eq!(receipt["envelope"]["summary"]["attack_id"], "T1046");
    assert_eq!(receipt["envelope"]["summary"]["tactic"], "discovery");
    assert_eq!(
        receipt["audit"][0]["prev"], "ev:genesis",
        "audit chain is rooted"
    );
    let handles = receipt["envelope"]["handles"].as_object().unwrap();
    assert!(!handles.is_empty(), "the open port is observed");
    let handle = handles.keys().next().unwrap().clone();
    std::fs::write(&receipt_path, &out).unwrap();

    // explain — resolve one observation handle out of the receipt.
    let (out, _, code) = vervet(&[
        "explain",
        "--run",
        receipt_path.to_str().unwrap(),
        "--handle",
        &handle,
    ]);
    assert_eq!(code, 0);
    assert!(
        out.contains(&format!("tcp/{port}")),
        "explain returns the record"
    );
    // A missing handle is an honest error, not a panic.
    assert_eq!(
        vervet(&[
            "explain",
            "--run",
            receipt_path.to_str().unwrap(),
            "--handle",
            "ev:nope",
        ])
        .2,
        1
    );

    // report — fold the stored receipt into a coverage map.
    let (out, _, code) = vervet(&["report", "--store", store, "--engagement", "cli-eng"]);
    assert_eq!(code, 0);
    let cov: Value = serde_json::from_str(&out).unwrap();
    assert!(
        cov["tactics"]["discovery"]
            .as_array()
            .unwrap()
            .iter()
            .any(|t| t == "T1046"),
        "coverage maps T1046 under discovery: {cov}"
    );

    // denial — a target outside the manifest scope exits 2, even reachable.
    let (_, err, code) = vervet(&[
        "emulate",
        "T1046",
        "--manifest",
        manifest,
        "--authority",
        &authority,
        "--target",
        "10.0.0.1",
        "--ports",
        &port,
    ]);
    assert_eq!(code, 2, "out-of-scope exits 2");
    assert!(err.contains("denied"));

    let _ = std::fs::remove_dir_all(&dir);
}
