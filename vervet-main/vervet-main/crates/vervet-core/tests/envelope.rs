//! The envelope assembles one handle per observation, deterministically.

use vervet_core::attack::{Tactic, TechniqueId};
use vervet_core::envelope::Envelope;
use vervet_core::evidence::Evidence;

fn sample() -> Evidence {
    let mut ev = Evidence::new(
        TechniqueId("T1046"),
        Tactic::Discovery,
        "Network Service Discovery",
        "eng-1",
    );
    ev.observe("port_open", "10.0.0.5", "tcp/22");
    ev.observe("port_open", "10.0.0.5", "tcp/445");
    ev
}

#[test]
fn one_handle_per_observation() {
    let env = Envelope::from_evidence(&sample()).unwrap();
    assert_eq!(env.summary.observation_count, 2);
    assert_eq!(env.handles.len(), 2);
    assert_eq!(env.summary.attack_id, "T1046");
    assert_eq!(env.summary.tactic, "discovery");
}

#[test]
fn handles_are_deterministic() {
    let a = Envelope::from_evidence(&sample()).unwrap();
    let b = Envelope::from_evidence(&sample()).unwrap();
    let ja = serde_json::to_string(&a.handles).unwrap();
    let jb = serde_json::to_string(&b.handles).unwrap();
    assert_eq!(ja, jb, "same evidence must yield byte-identical handles");
}
