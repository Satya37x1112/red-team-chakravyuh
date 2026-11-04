//! The receipt JSON Schema (`vervet schema`) is a hand-maintained part of the
//! contract, so it is prone to drifting from what `emulate` actually emits.
//! This test pins the two together: a real receipt must satisfy every
//! `required` key and `const` the published schema declares.

mod common;

use std::net::TcpListener;

use common::{vervet, write_manifest};
use serde_json::Value;

#[test]
fn an_emulated_receipt_conforms_to_the_published_schema() {
    let (schema_out, _, code) = vervet(&["schema"]);
    assert_eq!(code, 0);
    let schema: Value = serde_json::from_str(&schema_out).expect("schema is JSON");

    // Produce a real receipt against a loopback listener T1046 will find.
    let listener = TcpListener::bind(("127.0.0.1", 0)).unwrap();
    let port = listener.local_addr().unwrap().port().to_string();
    let dir = std::env::temp_dir().join(format!("vervet-schema-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let authority = write_manifest(&dir, "schema-eng", &["T1046"]);
    let manifest = dir.join("manifest.json");
    let (out, _, code) = vervet(&[
        "emulate",
        "T1046",
        "--manifest",
        manifest.to_str().unwrap(),
        "--authority",
        &authority,
        "--target",
        "127.0.0.1",
        "--ports",
        &port,
    ]);
    assert_eq!(code, 0);
    let receipt: Value = serde_json::from_str(&out).expect("receipt is JSON");

    conforms(&schema, &receipt, "receipt");

    let _ = std::fs::remove_dir_all(&dir);
}

/// A minimal, schema-driven conformance check: assert every `required` key is
/// present, every `const` matches, and recurse into object properties and array
/// items. Driven by the emitted schema, so a newly declared constraint is
/// enforced automatically without editing this test.
fn conforms(schema: &Value, value: &Value, path: &str) {
    if let Some(c) = schema.get("const") {
        assert_eq!(value, c, "const mismatch at {path}");
    }
    match schema.get("type").and_then(Value::as_str) {
        Some("object") => {
            for req in schema
                .get("required")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
            {
                let key = req.as_str().unwrap();
                assert!(
                    value.get(key).is_some(),
                    "missing required '{key}' at {path}"
                );
            }
            if let Some(props) = schema.get("properties").and_then(Value::as_object) {
                for (k, sub) in props {
                    if let Some(v) = value.get(k) {
                        conforms(sub, v, &format!("{path}.{k}"));
                    }
                }
            }
        }
        Some("array") => {
            if let (Some(items), Some(arr)) = (schema.get("items"), value.as_array()) {
                for (i, el) in arr.iter().enumerate() {
                    conforms(items, el, &format!("{path}[{i}]"));
                }
            }
        }
        _ => {}
    }
}
