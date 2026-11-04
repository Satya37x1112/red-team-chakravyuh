//! `vervet report` — synthesize receipts into an ATT&CK coverage map.

use std::process::ExitCode;

use serde_json::Value;
use vervet_report::{Coverage, coverage};
use vervet_store::Store;

use crate::args;

/// `vervet report <receipt.json ...>`  or  `vervet report --store <dir> [--engagement <id>]`
pub fn run_cmd(argv: &[String]) -> ExitCode {
    if let Some(dir) = args::value(argv, "--store") {
        return from_store(dir, args::value(argv, "--engagement"));
    }
    from_files(argv)
}

/// Aggregate every receipt in a run store, optionally filtered to one engagement.
fn from_store(dir: &str, engagement: Option<&str>) -> ExitCode {
    match Store::open(dir).load_all(engagement) {
        Ok(receipts) => emit(&coverage(&receipts)),
        Err(e) => {
            eprintln!("error: reading store {dir}: {e}");
            ExitCode::FAILURE
        }
    }
}

/// Aggregate receipts passed as file-path arguments.
fn from_files(argv: &[String]) -> ExitCode {
    let paths: Vec<&String> = argv.iter().filter(|a| !a.starts_with('-')).collect();
    if paths.is_empty() {
        eprintln!("usage: vervet report <receipt.json ...> | --store <dir> [--engagement <id>]");
        return ExitCode::FAILURE;
    }

    let mut receipts = Vec::with_capacity(paths.len());
    for path in paths {
        let text = match std::fs::read_to_string(path) {
            Ok(t) => t,
            Err(e) => {
                eprintln!("error: reading {path}: {e}");
                return ExitCode::FAILURE;
            }
        };
        match serde_json::from_str::<Value>(&text) {
            Ok(v) => receipts.push(v),
            Err(e) => {
                eprintln!("error: parsing {path}: {e}");
                return ExitCode::FAILURE;
            }
        }
    }
    emit(&coverage(&receipts))
}

fn emit(cov: &Coverage) -> ExitCode {
    println!(
        "{}",
        serde_json::to_string_pretty(cov).expect("coverage serialize")
    );
    ExitCode::SUCCESS
}
