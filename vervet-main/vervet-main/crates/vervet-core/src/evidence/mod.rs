//! Evidence: the typed result of an engagement, plus content-addressed handles.

pub mod hash;
pub mod record;

pub use hash::Handle;
pub use record::{Evidence, Observation};
