//! Iteration over the self-registered technique inventory.

use crate::Technique;

/// Every technique registered in the binary, in registration order.
pub fn all() -> impl Iterator<Item = &'static dyn Technique> {
    inventory::iter::<&'static dyn Technique>
        .into_iter()
        .copied()
}

/// Find a registered technique by its ATT&CK id, e.g. `T1046`.
pub fn find(attack_id: &str) -> Option<&'static dyn Technique> {
    all().find(|t| t.meta().id.as_str() == attack_id)
}
