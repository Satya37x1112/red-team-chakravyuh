//! T1110.003 — Password Spraying.

use std::collections::BTreeSet;

use vervet_core::attack::{Tactic, TechniqueId};
use vervet_core::evidence::Evidence;
use vervet_scope::Grant;
use vervet_technique::{SideEffect, Technique, TechniqueMeta};
use vervet_verify::judge;

/// Attempt one password across many accounts, at most one attempt per account,
/// to map weak-credential exposure without tripping lockout thresholds.
struct PasswordSpray;

const META: TechniqueMeta = TechniqueMeta {
    id: TechniqueId("T1110.003"),
    tactic: Tactic::CredentialAccess,
    name: "Password Spraying",
    summary: "Try one password across many accounts (at most one attempt each, to stay under lockout). On SSH ports it confirms the service, or asserts valid/invalid with the ssh-auth feature; elsewhere it checks reachability.",
    side_effect: SideEffect::Observable,
    inputs: &[
        "target",
        "port (default 445; 22/2022/2222 use the SSH backend)",
        "users (comma-separated)",
        "password",
    ],
};

const DEFAULT_PORT: u16 = 445;

impl Technique for PasswordSpray {
    fn meta(&self) -> &'static TechniqueMeta {
        &META
    }

    fn engage(&self, grant: &Grant) -> Evidence {
        let req = grant.request();
        let target = req.target.to_string();
        let mut ev = Evidence::new(META.id, META.tactic, META.name, grant.engagement_id());

        let Some(creds) = req.credentials.as_ref() else {
            ev.observe("spray_skipped", target.as_str(), "no credentials supplied");
            return ev;
        };

        let port = req.ports.first().copied().unwrap_or(DEFAULT_PORT);
        // One attempt per unique account: a repeated name never gets hit twice.
        for user in unique(&creds.usernames) {
            let verdict = judge(req.target, port, user, &creds.password);
            let banner = verdict
                .banner()
                .map(|b| format!(" banner={b:?}"))
                .unwrap_or_default();
            ev.observe(
                "auth_attempt",
                target.as_str(),
                format!(
                    "user={user} port={port} password=<redacted> verdict={}{}",
                    verdict.kind(),
                    banner
                ),
            );
        }
        ev
    }
}

/// Deduplicate usernames, preserving first-seen order, so a repeated account in
/// the input never receives more than one attempt.
fn unique(users: &[String]) -> Vec<&str> {
    let mut seen = BTreeSet::new();
    users
        .iter()
        .filter(|u| seen.insert(u.as_str()))
        .map(String::as_str)
        .collect()
}

inventory::submit!(&PasswordSpray as &dyn Technique);
