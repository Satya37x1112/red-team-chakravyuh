//! T1078 — Valid Accounts.

use vervet_core::attack::{Tactic, TechniqueId};
use vervet_core::evidence::Evidence;
use vervet_scope::Grant;
use vervet_technique::{SideEffect, Technique, TechniqueMeta};
use vervet_verify::judge;

/// Check which of a set of known username/password pairs still authenticate —
/// the surviving footholds. Unlike spraying, each account carries its own
/// password.
struct ValidAccounts;

const META: TechniqueMeta = TechniqueMeta {
    id: TechniqueId("T1078"),
    tactic: Tactic::InitialAccess,
    name: "Valid Accounts",
    summary: "Confirm which known username/password pairs still authenticate against an in-scope service. On SSH ports it confirms the service, or asserts valid/invalid with the ssh-auth feature; elsewhere it checks reachability.",
    side_effect: SideEffect::Observable,
    inputs: &["target", "port (default 22)", "pairs (user:pass,user:pass)"],
};

const DEFAULT_PORT: u16 = 22;

impl Technique for ValidAccounts {
    fn meta(&self) -> &'static TechniqueMeta {
        &META
    }

    fn engage(&self, grant: &Grant) -> Evidence {
        let req = grant.request();
        let target = req.target.to_string();
        let mut ev = Evidence::new(META.id, META.tactic, META.name, grant.engagement_id());

        let pairs = match req.credentials.as_ref() {
            Some(c) if !c.pairs.is_empty() => &c.pairs,
            _ => {
                ev.observe(
                    "check_skipped",
                    target.as_str(),
                    "no credential pairs supplied (use --pairs user:pass,...)",
                );
                return ev;
            }
        };

        let port = req.ports.first().copied().unwrap_or(DEFAULT_PORT);
        for pair in pairs {
            let verdict = judge(req.target, port, &pair.username, &pair.password);
            let banner = verdict
                .banner()
                .map(|b| format!(" banner={b:?}"))
                .unwrap_or_default();
            ev.observe(
                "account_check",
                target.as_str(),
                format!(
                    "user={} port={port} password=<redacted> verdict={}{}",
                    pair.username,
                    verdict.kind(),
                    banner
                ),
            );
        }
        ev
    }
}

inventory::submit!(&ValidAccounts as &dyn Technique);
