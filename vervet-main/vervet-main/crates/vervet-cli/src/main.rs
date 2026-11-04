//! The vervet binary. Parses the verb and hands off to one focused module.

use std::process::ExitCode;

mod args;
mod describe;
mod emulate;
mod explain;
mod help;
mod report;
mod schema;

// Force-link the technique crate so its `inventory::submit!` entries register.
use vervet_techniques as _;

fn main() -> ExitCode {
    let argv: Vec<String> = std::env::args().skip(1).collect();
    match argv.first().map(String::as_str) {
        Some("describe") => describe::run(),
        Some("schema") => schema::run(),
        Some("emulate") => emulate::run_cmd(&argv[1..]),
        Some("report") => report::run_cmd(&argv[1..]),
        Some("explain") => explain::run(&argv[1..]),
        Some("help") | Some("--help") | Some("-h") => help::run(),
        Some("--version") | Some("-V") => {
            println!("vervet {}", env!("CARGO_PKG_VERSION"));
            ExitCode::SUCCESS
        }
        Some(verb) => {
            eprintln!("error: unknown verb '{verb}'");
            eprintln!("run `vervet help` for the verb surface");
            ExitCode::FAILURE
        }
        None => {
            eprintln!("usage: vervet <describe|schema|emulate|report|explain> [args]");
            eprintln!("run `vervet help` for details");
            ExitCode::FAILURE
        }
    }
}
