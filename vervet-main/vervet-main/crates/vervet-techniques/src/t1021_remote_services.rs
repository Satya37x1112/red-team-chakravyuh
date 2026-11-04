//! T1021 — Remote Services.

use vervet_core::attack::{Tactic, TechniqueId};
use vervet_core::evidence::Evidence;
use vervet_scope::Grant;
use vervet_technique::{SideEffect, Technique, TechniqueMeta};
use vervet_verify::{Reachability, SshProbe, Verifier};

/// Map which remote-access services are reachable from this foothold — the
/// lateral-movement surface. v0 confirms reachability (and SSH by banner); it
/// does not move laterally or authenticate.
struct RemoteServices;

const META: TechniqueMeta = TechniqueMeta {
    id: TechniqueId("T1021"),
    tactic: Tactic::LateralMovement,
    name: "Remote Services",
    summary: "Check which remote-access services (SMB/SSH/RDP) answer on an in-scope host — the reachable lateral-movement surface. Confirms reachability and SSH service; does not authenticate or move laterally.",
    side_effect: SideEffect::Observable,
    inputs: &["target", "ports (default 445,22,3389 = SMB,SSH,RDP)"],
};

/// The classic lateral-movement service ports, probed when none are given.
const DEFAULT_PORTS: &[u16] = &[445, 22, 3389];
/// Ports on which we run the real SSH protocol probe rather than a bare connect.
const SSH_PORTS: &[u16] = &[22, 2022, 2222];

impl Technique for RemoteServices {
    fn meta(&self) -> &'static TechniqueMeta {
        &META
    }

    fn engage(&self, grant: &Grant) -> Evidence {
        let req = grant.request();
        let target = req.target.to_string();
        let mut ev = Evidence::new(META.id, META.tactic, META.name, grant.engagement_id());

        let ports = if req.ports.is_empty() {
            DEFAULT_PORTS
        } else {
            req.ports.as_slice()
        };
        for &port in ports {
            let verifier: &dyn Verifier = if SSH_PORTS.contains(&port) {
                &SshProbe
            } else {
                &Reachability
            };
            let verdict = verifier.verify(req.target, port, "", "");
            let banner = verdict
                .banner()
                .map(|b| format!(" banner={b:?}"))
                .unwrap_or_default();
            ev.observe(
                "remote_service",
                target.as_str(),
                format!(
                    "port={port} service={} verdict={}{}",
                    service_name(port),
                    verdict.kind(),
                    banner
                ),
            );
        }
        ev
    }
}

/// A short label for a well-known remote-service port.
fn service_name(port: u16) -> &'static str {
    match port {
        22 | 2022 | 2222 => "ssh",
        139 => "netbios",
        445 => "smb",
        3389 => "rdp",
        5985 | 5986 => "winrm",
        _ => "tcp",
    }
}

inventory::submit!(&RemoteServices as &dyn Technique);
