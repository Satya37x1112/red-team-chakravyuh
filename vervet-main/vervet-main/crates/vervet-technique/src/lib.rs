#![deny(missing_docs)]

//! The technique contract. Every emulation primitive implements [`Technique`]
//! and registers itself via [`inventory`], so adding a technique is adding one
//! file — no central dispatch is ever edited.

pub mod meta;
pub mod registry;

pub use meta::{SideEffect, TechniqueMeta};
pub use registry::{all, find};

use vervet_core::evidence::Evidence;
use vervet_scope::Grant;

/// One ATT&CK technique vervet can emulate.
///
/// `engage` takes a [`Grant`] — an unforgeable proof of authorization that only
/// [`vervet_scope::Gate`] can mint — so a technique is structurally incapable
/// of acting outside an approved scope.
pub trait Technique: Sync {
    /// Static, self-describing metadata for `describe` and `schema`.
    fn meta(&self) -> &'static TechniqueMeta;

    /// Execute the technique against the granted target, returning evidence.
    fn engage(&self, grant: &Grant) -> Evidence;
}

inventory::collect!(&'static dyn Technique);
