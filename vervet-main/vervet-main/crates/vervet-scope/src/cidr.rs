//! IPv4 CIDR membership, dependency-free.

use std::net::Ipv4Addr;

/// An IPv4 CIDR block, e.g. `10.0.0.0/24`.
#[derive(Clone, Copy, Debug)]
pub struct Cidr {
    base: u32,
    mask: u32,
}

impl Cidr {
    /// Parse `a.b.c.d/prefix`. Returns `None` on malformed input.
    pub fn parse(s: &str) -> Option<Cidr> {
        let (addr, prefix) = s.split_once('/')?;
        let addr: Ipv4Addr = addr.parse().ok()?;
        let prefix: u32 = prefix.parse().ok()?;
        if prefix > 32 {
            return None;
        }
        let mask = if prefix == 0 {
            0
        } else {
            u32::MAX << (32 - prefix)
        };
        Some(Cidr {
            base: u32::from(addr) & mask,
            mask,
        })
    }

    /// Whether `ip` falls within this block.
    pub fn contains(&self, ip: Ipv4Addr) -> bool {
        (u32::from(ip) & self.mask) == self.base
    }
}
