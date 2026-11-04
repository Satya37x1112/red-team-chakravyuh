//! The store round-trips receipts, filters by engagement, and is idempotent.

use std::fs;
use std::path::PathBuf;

use serde_json::json;
use vervet_store::Store;

fn tmp(name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("vervet-store-{}-{name}", std::process::id()));
    let _ = fs::remove_dir_all(&dir);
    dir
}

fn receipt(engagement: &str, attack_id: &str) -> serde_json::Value {
    json!({
        "envelope": {
            "summary": {
                "name": "x",
                "attack_id": attack_id,
                "tactic": "discovery",
                "engagement_id": engagement,
                "observation_count": 1
            }
        },
        "audit": []
    })
}

#[test]
fn put_then_load_filters_by_engagement() {
    let root = tmp("filter");
    let store = Store::open(&root);

    let r = store.put(&receipt("eng-a", "T1046")).unwrap();
    assert_eq!(r.engagement_id, "eng-a");
    store.put(&receipt("eng-b", "T1021")).unwrap();

    assert_eq!(store.load_all(None).unwrap().len(), 2);
    assert_eq!(store.load_all(Some("eng-a")).unwrap().len(), 1);
    assert_eq!(store.load_all(Some("nope")).unwrap().len(), 0);

    let _ = fs::remove_dir_all(&root);
}

#[test]
fn storing_the_same_receipt_is_idempotent() {
    let root = tmp("idem");
    let store = Store::open(&root);

    let a = store.put(&receipt("eng-a", "T1046")).unwrap();
    let b = store.put(&receipt("eng-a", "T1046")).unwrap();
    assert_eq!(a.run_id, b.run_id, "same content yields the same run id");
    assert_eq!(
        store.load_all(None).unwrap().len(),
        1,
        "overwritten, not duplicated"
    );

    let _ = fs::remove_dir_all(&root);
}
