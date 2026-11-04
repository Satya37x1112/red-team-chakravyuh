//! T1046 — Network Service Discovery.

use std::net::{IpAddr, SocketAddr, TcpStream};
use std::time::Duration;

use vervet_core::attack::{Tactic, TechniqueId};
use vervet_core::evidence::Evidence;
use vervet_scope::Grant;
use vervet_technique::{SideEffect, Technique, TechniqueMeta};

/// Establishes TCP connections to a small set of common service ports on the
/// granted target and records which answer.
struct ServiceDiscovery;

const META: TechniqueMeta = TechniqueMeta {
    id: TechniqueId("T1046"),
    tactic: Tactic::Discovery,
    name: "Network Service Discovery",
    summary: "Probe common TCP service ports on an in-scope host to map reachable services.",
    side_effect: SideEffect::Observable,
    inputs: &["target", "ports (optional; default common service ports)"],
};

/// Ports probed when a request does not specify its own set.
const DEFAULT_PORTS: &[u16] = &[22, 80, 135, 139, 445, 3389];

const CONNECT_TIMEOUT: Duration = Duration::from_millis(400);

impl Technique for ServiceDiscovery {
    fn meta(&self) -> &'static TechniqueMeta {
        &META
    }

    fn engage(&self, grant: &Grant) -> Evidence {
        let req = grant.request();
        let mut ev = Evidence::new(META.id, META.tactic, META.name, grant.engagement_id());
        let ports = if req.ports.is_empty() {
            DEFAULT_PORTS
        } else {
            req.ports.as_slice()
        };
        let target = IpAddr::V4(req.target);
        for &port in ports {
            let addr = SocketAddr::new(target, port);
            if TcpStream::connect_timeout(&addr, CONNECT_TIMEOUT).is_ok() {
                ev.observe("port_open", req.target.to_string(), format!("tcp/{port}"));
            }
        }
        ev
    }
}

inventory::submit!(&ServiceDiscovery as &dyn Technique);
