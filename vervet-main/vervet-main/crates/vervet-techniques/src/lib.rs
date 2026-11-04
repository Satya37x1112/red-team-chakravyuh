#![deny(missing_docs)]

//! Registered emulation techniques. Each technique is one self-contained file
//! that submits itself to the registry; this `lib.rs` only lists the modules.
//!
//! Add a technique = add one file here and one `mod` line. Nothing else in the
//! workspace changes: `describe`, `schema`, dispatch and reporting all read the
//! inventory.

mod t1021_remote_services;
mod t1046_service_discovery;
mod t1078_valid_accounts;
mod t1110_003_password_spray;
