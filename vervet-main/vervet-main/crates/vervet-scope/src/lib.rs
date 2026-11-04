#![deny(missing_docs)]

//! Authorization spine. Every state-changing technique must pass through this
//! crate to obtain a [`Grant`] — an unforgeable capability token. No technique
//! can construct a `Grant` itself, so no technique can act out of scope.

pub mod audit;
pub mod cidr;
pub mod credentials;
pub mod gate;
pub mod grant;
pub mod manifest;

pub use audit::AuditEntry;
pub use credentials::{Credential, Credentials};
pub use gate::{Denied, Gate};
pub use grant::{Grant, Request};
pub use manifest::{Claims, Manifest};
