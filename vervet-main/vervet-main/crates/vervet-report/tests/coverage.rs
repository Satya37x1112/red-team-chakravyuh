//! Coverage rolls receipts up by tactic and sums evidence, honestly.

use serde_json::json;
use vervet_report::coverage;

fn receipt(attack_id: &str, name: &str, tactic: &str, observations: u64) -> serde_json::Value {
    json!({
        "envelope": {
            "summary": {
                "name": name,
                "attack_id": attack_id,
                "tactic": tactic,
                "engagement_id": "e",
                "observation_count": observations
            }
        },
        "audit": []
    })
}

#[test]
fn groups_by_tactic_and_sums_observations() {
    let receipts = vec![
        receipt("T1046", "Network Service Discovery", "discovery", 3),
        receipt("T1046", "Network Service Discovery", "discovery", 2),
        receipt("T1110.003", "Password Spraying", "credential_access", 4),
    ];
    let cov = coverage(&receipts);

    assert_eq!(cov.totals.techniques, 2);
    assert_eq!(cov.totals.engagements, 3);
    assert_eq!(cov.totals.observations, 9);

    let t1046 = cov.techniques.iter().find(|t| t.id == "T1046").unwrap();
    assert_eq!(
        t1046.engagements, 2,
        "two receipts collapse into one technique"
    );
    assert_eq!(t1046.observations, 5);
    assert_eq!(t1046.detection, "unobserved");

    assert_eq!(cov.tactics["discovery"], vec!["T1046"]);
    assert_eq!(cov.tactics["credential_access"], vec!["T1110.003"]);
}

#[test]
fn skips_receipts_without_a_summary() {
    let receipts = vec![
        json!({"garbage": true}),
        receipt("T1046", "x", "discovery", 1),
    ];
    let cov = coverage(&receipts);
    assert_eq!(cov.totals.techniques, 1);
}
