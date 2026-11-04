//! `vervet emulate <ATTACK_ID>` — authorize and fire any registered technique.

use std::net::Ipv4Addr;
use std::process::ExitCode;
use std::time::{SystemTime, UNIX_EPOCH};

use vervet_engage::{EngageError, Receipt, run};
use vervet_scope::{Credential, Credentials, Gate, Manifest, Request};
use vervet_store::{RunRef, Store};
use vervet_technique::find;

use crate::args;

const USAGE: &str = "usage: vervet emulate <ATTACK_ID> --manifest <f> --authority <hex> \
--target <ipv4> [--ports a,b] [--users u1,u2] [--password p] [--pairs u:p,u:p] [--store dir]";

/// Emits an audited engagement receipt for the named technique. A denial prints
/// the typed reason and exits 2; usage/IO errors exit 1.
pub fn run_cmd(argv: &[String]) -> ExitCode {
    let Some(attack_id) = argv.first().filter(|a| !a.starts_with('-')) else {
        eprintln!("{USAGE}");
        return ExitCode::FAILURE;
    };
    let rest = &argv[1..];

    let (Some(manifest_path), Some(authority), Some(target)) = (
        args::value(rest, "--manifest"),
        args::value(rest, "--authority"),
        args::value(rest, "--target"),
    ) else {
        eprintln!("{USAGE}");
        return ExitCode::FAILURE;
    };
    let Ok(target) = target.parse::<Ipv4Addr>() else {
        eprintln!("error: --target must be an IPv4 address");
        return ExitCode::FAILURE;
    };
    let ports = args::value(rest, "--ports")
        .map(parse_ports)
        .unwrap_or_default();

    let manifest = match load_manifest(manifest_path) {
        Ok(m) => m,
        Err(e) => return fail(&e),
    };
    let gate = match Gate::new(authority) {
        Ok(g) => g,
        Err(d) => return deny(&d.to_string()),
    };
    let Some(technique) = find(attack_id) else {
        return fail(&format!("{attack_id} is not a registered technique"));
    };

    let mut request = Request::new(target, ports);
    if let Some(creds) = credentials(rest) {
        request = request.with_credentials(creds);
    }

    match run(&gate, &manifest, technique, request, now()) {
        Ok(receipt) => {
            if let Some(dir) = store_dir(rest) {
                match persist(&dir, &receipt) {
                    Ok(r) => eprintln!("stored: {} ({})", r.path.display(), r.run_id),
                    Err(e) => eprintln!("warning: could not store receipt: {e}"),
                }
            }
            println!(
                "{}",
                serde_json::to_string_pretty(&receipt).expect("receipt serialize")
            );
            ExitCode::SUCCESS
        }
        Err(EngageError::Denied(d)) => deny(&d.to_string()),
        Err(EngageError::Assembly(e)) => fail(&e.to_string()),
    }
}

/// Store directory from `--store`, falling back to the `VERVET_STORE` env var.
fn store_dir(args: &[String]) -> Option<String> {
    args::value(args, "--store")
        .map(String::from)
        .or_else(|| std::env::var("VERVET_STORE").ok())
}

/// Persist a receipt to the run store.
fn persist(dir: &str, receipt: &Receipt) -> Result<RunRef, String> {
    let value = serde_json::to_value(receipt).map_err(|e| e.to_string())?;
    Store::open(dir).put(&value).map_err(|e| e.to_string())
}

/// Build credentials from the spray flags (`--users` + `--password`) and/or the
/// per-account `--pairs` flag. Returns `None` when no credential input is given.
fn credentials(args: &[String]) -> Option<Credentials> {
    let password = args::value(args, "--password");
    let pairs = parse_pairs(args::value(args, "--pairs"));
    if password.is_none() && pairs.is_empty() {
        return None;
    }
    let usernames = args::value(args, "--users")
        .map(|s| {
            s.split(',')
                .map(|u| u.trim().to_string())
                .filter(|u| !u.is_empty())
                .collect()
        })
        .unwrap_or_default();
    Some(Credentials {
        usernames,
        password: password.unwrap_or_default().to_string(),
        pairs,
    })
}

/// Parse `user:pass,user:pass` into credential pairs. The password keeps any
/// colons after the first separator.
fn parse_pairs(spec: Option<&str>) -> Vec<Credential> {
    spec.map(|s| {
        s.split(',')
            .filter_map(|item| {
                let (user, pass) = item.split_once(':')?;
                let user = user.trim();
                if user.is_empty() {
                    return None;
                }
                Some(Credential {
                    username: user.to_string(),
                    password: pass.to_string(),
                })
            })
            .collect()
    })
    .unwrap_or_default()
}

fn now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

fn parse_ports(s: &str) -> Vec<u16> {
    s.split(',').filter_map(|p| p.trim().parse().ok()).collect()
}

fn load_manifest(path: &str) -> Result<Manifest, String> {
    let text = std::fs::read_to_string(path).map_err(|e| format!("reading {path}: {e}"))?;
    serde_json::from_str(&text).map_err(|e| format!("parsing {path}: {e}"))
}

fn fail(msg: &str) -> ExitCode {
    eprintln!("error: {msg}");
    ExitCode::FAILURE
}

fn deny(msg: &str) -> ExitCode {
    eprintln!("denied: {msg}");
    ExitCode::from(2)
}
