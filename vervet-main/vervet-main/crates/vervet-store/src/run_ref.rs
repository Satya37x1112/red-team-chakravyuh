//! A reference to one stored receipt.

use std::path::PathBuf;

/// Where a receipt landed and how to name it: the engagement it belongs to, its
/// content-addressed run id, and the file path on disk.
#[derive(Clone, Debug)]
pub struct RunRef {
    /// The engagement the receipt was filed under.
    pub engagement_id: String,
    /// Content-addressed run id, a blake3 of the receipt.
    pub run_id: String,
    /// Where the receipt was written on disk.
    pub path: PathBuf,
}
