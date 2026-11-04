//! Properties of the tamper-evident audit chain. The handle is a blake3 commit
//! over (seq, engagement_id, action, prev); any change to those inputs must
//! change the handle, and a chain links each entry to the recomputed handle of
//! its predecessor.

use proptest::prelude::*;
use vervet_core::evidence::Handle;
use vervet_scope::AuditEntry;

/// The handle of an entry, as the string the next entry would store as `prev`.
fn handle_of(entry: &AuditEntry) -> String {
    Handle::of(entry).unwrap().as_str().to_string()
}

proptest! {
    /// Determinism: identical inputs yield identical handles.
    #[test]
    fn append_is_deterministic(seq in any::<u64>(), eng in ".*", action in ".*", prev in ".*") {
        let (_, h1) = AuditEntry::append(seq, &eng, &action, &prev);
        let (_, h2) = AuditEntry::append(seq, &eng, &action, &prev);
        prop_assert_eq!(h1.as_str(), h2.as_str());
    }

    /// Tamper sensitivity: two distinct input tuples produce distinct handles
    /// (with overwhelming probability — the handle is a 64-bit blake3 prefix).
    #[test]
    fn distinct_inputs_distinct_handles(
        a in (any::<u64>(), ".*", ".*", ".*"),
        b in (any::<u64>(), ".*", ".*", ".*"),
    ) {
        prop_assume!(a != b);
        let (_, ha) = AuditEntry::append(a.0, &a.1, &a.2, &a.3);
        let (_, hb) = AuditEntry::append(b.0, &b.1, &b.2, &b.3);
        prop_assert_ne!(ha.as_str(), hb.as_str());
    }

    /// Changing any single one of the four inputs changes the handle.
    #[test]
    fn each_field_affects_handle(
        seq in any::<u64>(),
        eng in ".*",
        action in ".*",
        prev in ".*",
        d_seq in any::<u64>(),
        d_eng in ".*",
        d_action in ".*",
        d_prev in ".*",
    ) {
        let (base, hb) = AuditEntry::append(seq, &eng, &action, &prev);
        let base_h = handle_of(&base);
        prop_assert_eq!(hb.as_str(), &base_h);

        if d_seq != seq {
            let (_, h) = AuditEntry::append(d_seq, &eng, &action, &prev);
            prop_assert_ne!(h.as_str(), &base_h);
        }
        if d_eng != eng {
            let (_, h) = AuditEntry::append(seq, &d_eng, &action, &prev);
            prop_assert_ne!(h.as_str(), &base_h);
        }
        if d_action != action {
            let (_, h) = AuditEntry::append(seq, &eng, &d_action, &prev);
            prop_assert_ne!(h.as_str(), &base_h);
        }
        if d_prev != prev {
            let (_, h) = AuditEntry::append(seq, &eng, &action, &d_prev);
            prop_assert_ne!(h.as_str(), &base_h);
        }
    }

    /// Chain linkage: each entry's `prev` (after genesis) equals the recomputed
    /// handle of its predecessor — so the whole chain re-verifies.
    #[test]
    fn chain_links_verify(eng in ".*", actions in prop::collection::vec(".*", 1..12)) {
        let mut prev = AuditEntry::GENESIS.to_string();
        let mut chain = Vec::new();
        for (i, action) in actions.iter().enumerate() {
            let (entry, handle) = AuditEntry::append(i as u64, &eng, action, &prev);
            chain.push(entry);
            prev = handle.as_str().to_string();
        }

        prop_assert_eq!(&chain[0].prev, AuditEntry::GENESIS);
        for w in chain.windows(2) {
            prop_assert_eq!(&w[1].prev, &handle_of(&w[0]));
        }
    }

    /// Tampering breaks the chain: mutating entry k's action makes entry k+1's
    /// stored `prev` no longer match the recomputed handle of entry k.
    #[test]
    fn mutation_breaks_linkage(
        eng in ".*",
        actions in prop::collection::vec(".*", 2..12),
        tamper in ".*",
    ) {
        let mut prev = AuditEntry::GENESIS.to_string();
        let mut chain = Vec::new();
        for (i, action) in actions.iter().enumerate() {
            let (entry, handle) = AuditEntry::append(i as u64, &eng, action, &prev);
            chain.push(entry);
            prev = handle.as_str().to_string();
        }

        // Mutate the first entry's action; assume it actually changes.
        prop_assume!(chain[0].action != tamper);
        let stored_prev = chain[1].prev.clone();
        chain[0].action = tamper;
        prop_assert_ne!(handle_of(&chain[0]), stored_prev);
    }
}
