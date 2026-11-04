//! Properties of IPv4 CIDR membership. The mask math here is derived
//! independently of the impl so the assertions check observable behaviour, not
//! the internal representation (`base`/`mask` are private anyway).

use std::net::Ipv4Addr;

use proptest::prelude::*;
use vervet_scope::cidr::Cidr;

/// The network mask for a prefix, computed independently of `Cidr`'s internals.
fn mask_for(prefix: u32) -> u32 {
    if prefix == 0 {
        0
    } else {
        u32::MAX << (32 - prefix)
    }
}

proptest! {
    /// A `/32` block contains exactly its own base address.
    #[test]
    fn slash32_contains_only_its_base(addr in any::<u32>()) {
        let ip = Ipv4Addr::from(addr);
        let block = Cidr::parse(&format!("{ip}/32")).unwrap();
        prop_assert!(block.contains(ip));
    }

    /// A `/32` does not contain a different address.
    #[test]
    fn slash32_excludes_other(a in any::<u32>(), b in any::<u32>()) {
        prop_assume!(a != b);
        let block = Cidr::parse(&format!("{}/32", Ipv4Addr::from(a))).unwrap();
        prop_assert!(!block.contains(Ipv4Addr::from(b)));
    }

    /// `0.0.0.0/0` contains every address.
    #[test]
    fn zero_prefix_contains_everything(addr in any::<u32>()) {
        let block = Cidr::parse("0.0.0.0/0").unwrap();
        prop_assert!(block.contains(Ipv4Addr::from(addr)));
    }

    /// Containment matches independently-derived mask math for any block and ip:
    /// `contains(ip) <=> (ip & mask) == (base & mask)`.
    #[test]
    fn containment_matches_mask_math(base in any::<u32>(), ip in any::<u32>(), p in 0u32..=32) {
        let block = Cidr::parse(&format!("{}/{p}", Ipv4Addr::from(base))).unwrap();
        let mask = mask_for(p);
        let expected = (ip & mask) == (base & mask);
        prop_assert_eq!(block.contains(Ipv4Addr::from(ip)), expected);
    }

    /// Varying only host bits stays inside the block; flipping any network bit
    /// (when one exists, i.e. prefix < 32) leaves it.
    #[test]
    fn host_bits_in_network_bits_out(base in any::<u32>(), host_noise in any::<u32>(), p in 0u32..=32) {
        let mask = mask_for(p);
        let block = Cidr::parse(&format!("{}/{p}", Ipv4Addr::from(base))).unwrap();

        // Take the block's network and vary only host bits -> still contained.
        let network = base & mask;
        let varied = network | (host_noise & !mask);
        prop_assert!(block.contains(Ipv4Addr::from(varied)));

        // Flip the highest network bit -> no longer contained (prefix >= 1).
        if p >= 1 {
            let net_bit = 1u32 << (32 - p);
            prop_assert!(!block.contains(Ipv4Addr::from(network ^ net_bit)));
        }
    }

    /// Round-trip: an address is always contained in the /prefix block whose
    /// base is that address masked to the prefix.
    #[test]
    fn address_in_its_own_masked_block(addr in any::<u32>(), p in 0u32..=32) {
        let masked = addr & mask_for(p);
        let block = Cidr::parse(&format!("{}/{p}", Ipv4Addr::from(masked))).unwrap();
        prop_assert!(block.contains(Ipv4Addr::from(addr)));
    }

    /// parse rejects any prefix > 32.
    #[test]
    fn rejects_oversized_prefix(addr in any::<u32>(), p in 33u32..=255) {
        let block = Cidr::parse(&format!("{}/{p}", Ipv4Addr::from(addr)));
        prop_assert!(block.is_none());
    }
}
