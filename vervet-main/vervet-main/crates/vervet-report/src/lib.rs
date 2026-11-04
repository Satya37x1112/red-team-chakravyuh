#![deny(missing_docs)]

//! Coverage reporting. Folds a set of engagement receipts into an ATT&CK
//! coverage map — which techniques and tactics were exercised, how often, and
//! how much evidence each produced. Pure aggregation over receipt JSON: no
//! registry lookup, so it works on historical receipts unchanged.

pub mod build;
pub mod coverage;

pub use build::coverage;
pub use coverage::{Coverage, TechniqueCoverage, Totals};
