//! The vq1 evidence envelope: a dense, self-describing wrapper an AI consumer
//! reads top-down — header, summary, then handle-addressable records.

pub mod document;
pub mod handle;
pub mod header;
pub mod summary;

pub use document::Envelope;
pub use handle::HandleMap;
pub use header::Header;
pub use summary::Summary;
