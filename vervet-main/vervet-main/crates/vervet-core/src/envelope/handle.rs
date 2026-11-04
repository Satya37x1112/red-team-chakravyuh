//! Handle-addressable drill-down storage.

use std::collections::BTreeMap;

use serde::Serialize;
use serde_json::Value;

/// Maps each evidence handle to its full record. A `BTreeMap` keeps key order
/// deterministic across serializations.
#[derive(Clone, Debug, Default, Serialize)]
pub struct HandleMap(BTreeMap<String, Value>);

impl HandleMap {
    /// Insert a record under its handle.
    pub fn insert(&mut self, handle: impl Into<String>, record: Value) {
        self.0.insert(handle.into(), record);
    }

    /// Look up a record by handle.
    pub fn get(&self, handle: &str) -> Option<&Value> {
        self.0.get(handle)
    }

    /// Number of stored records.
    pub fn len(&self) -> usize {
        self.0.len()
    }

    /// Whether the map holds no records.
    pub fn is_empty(&self) -> bool {
        self.0.is_empty()
    }
}
