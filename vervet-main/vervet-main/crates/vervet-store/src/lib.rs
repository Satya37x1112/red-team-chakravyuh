#![deny(missing_docs)]

//! Receipt persistence: a content-addressed run store on the local filesystem.
//!
//! `emulate` writes each receipt here; `report` reads them back. Receipts are
//! grouped by engagement and named by a blake3 of their content, so storing the
//! same receipt twice is idempotent and a run id is stable across machines.

pub mod run_ref;
pub mod store;

pub use run_ref::RunRef;
pub use store::Store;
