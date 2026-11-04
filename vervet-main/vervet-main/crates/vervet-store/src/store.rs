//! The filesystem run store.

use std::fs;
use std::io;
use std::path::PathBuf;

use serde_json::Value;

use crate::run_ref::RunRef;

/// A run store rooted at a directory. Layout: `<root>/<engagement>/<id>.json`.
pub struct Store {
    root: PathBuf,
}

impl Store {
    /// Open a store rooted at `root` (created lazily on first write).
    pub fn open(root: impl Into<PathBuf>) -> Self {
        Store { root: root.into() }
    }

    /// Persist a receipt, returning a content-addressed run reference. Storing
    /// the same receipt twice is idempotent — same content, same run id, same
    /// path overwritten.
    pub fn put(&self, receipt: &Value) -> io::Result<RunRef> {
        let engagement = engagement_of(receipt).unwrap_or("unknown").to_string();
        let bytes = serde_json::to_vec_pretty(receipt)?;
        let run_id = format!("run:{}", &blake3::hash(&bytes).to_hex()[..16]);
        let dir = self.root.join(&engagement);
        fs::create_dir_all(&dir)?;
        let path = dir.join(format!("{}.json", &run_id[4..]));
        fs::write(&path, &bytes)?;
        Ok(RunRef {
            engagement_id: engagement,
            run_id,
            path,
        })
    }

    /// Load every stored receipt, optionally filtered to one engagement.
    pub fn load_all(&self, engagement: Option<&str>) -> io::Result<Vec<Value>> {
        let mut out = Vec::new();
        for dir in self.engagement_dirs(engagement)? {
            for entry in fs::read_dir(&dir)? {
                let path = entry?.path();
                if path.extension().is_some_and(|e| e == "json") {
                    let text = fs::read_to_string(&path)?;
                    if let Ok(value) = serde_json::from_str(&text) {
                        out.push(value);
                    }
                }
            }
        }
        Ok(out)
    }

    /// The engagement subdirectories to scan: one, or all that exist.
    fn engagement_dirs(&self, engagement: Option<&str>) -> io::Result<Vec<PathBuf>> {
        if let Some(name) = engagement {
            let dir = self.root.join(name);
            return Ok(if dir.is_dir() { vec![dir] } else { vec![] });
        }
        let mut dirs = Vec::new();
        if !self.root.is_dir() {
            return Ok(dirs);
        }
        for entry in fs::read_dir(&self.root)? {
            let path = entry?.path();
            if path.is_dir() {
                dirs.push(path);
            }
        }
        Ok(dirs)
    }
}

/// Pull the engagement id out of a receipt's summary.
fn engagement_of(receipt: &Value) -> Option<&str> {
    receipt
        .get("envelope")?
        .get("summary")?
        .get("engagement_id")?
        .as_str()
}
