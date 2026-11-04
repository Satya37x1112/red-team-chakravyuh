#![deny(missing_docs)]

//! Foundational types for vervet: ATT&CK identifiers, the vq1 evidence
//! envelope, and content-addressed evidence records.
//!
//! No vervet crate sits below this one. Every file owns exactly one concept;
//! `mod.rs` files re-export and contain no logic.

pub mod attack;
pub mod envelope;
pub mod error;
pub mod evidence;

pub use error::Error;
