#![deny(missing_docs)]

//! The engagement orchestration primitive. `run` is the single canonical path
//! from a signed manifest to an audited [`Receipt`]: it authorizes the request
//! through the gate, engages the technique, and binds the evidence envelope to
//! a tamper-evident audit chain. Every verb that fires a technique funnels
//! through here, so auditing can never be forgotten.

pub mod error;
pub mod receipt;
pub mod run;

pub use error::EngageError;
pub use receipt::Receipt;
pub use run::run;
