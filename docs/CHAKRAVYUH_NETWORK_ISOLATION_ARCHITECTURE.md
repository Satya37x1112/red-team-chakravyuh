# CYBER CHAKRAVYUH — Isolated Lab Network: Feasibility Assessment

**Author:** Implementation engineer (Claude Code, on Kali) — read-only assessment
**Date:** 2026-11-08
**Nature:** READ-ONLY feasibility report. **No host networking, firewall, VMware, or Windows settings were changed. No live testing.** This is a design + advisory report; the owner performs the actual host/VMware/Windows configuration after approval.

Goal (owner-approved): a **dedicated, isolated lab network** between the Kali attacker VM and a separate physical Windows target laptop, with **internet (for OmniRoute/AI) kept on a separate path**, and **no unintended exposure of the Windows target to external networks**.

---

## 1. What was observed (from inside the Kali guest — read-only)

| Item | Observed |
|---|---|
| NICs presented to Kali | **One** virtual NIC: `eth0` (Intel 82545EM = VMware **e1000**), MAC `00:0c:29:b4:30:b3` (VMware OUI) |
| Addressing | `eth0 = 192.168.176.131/24`, default gateway `192.168.176.2`, DNS `192.168.176.2` |
| Gateway identity | gateway MAC `00:50:56:e0:7a:32` → **VMware** OUI ⇒ this is the **VMware NAT device (vmnet8)** |
| NetworkManager | `eth0` = "Wired connection 1", connected |
| Current VMware mode | **NAT** (single adapter) |

**Honest limitations (cannot be seen from inside the guest):**
- The **host laptop's** physical interfaces (Wi‑Fi, built-in Ethernet, USB‑Ethernet) — not visible to the guest.
- **VMware host-side** settings (whether bridged is available, vmnet mapping) — host-side only.
- The **Windows target laptop** — a separate machine, not inspectable from here.

These must be checked by the owner on the **host** (`VMware → Edit → Virtual Network Editor`, and the host OS network settings).

---

## 2. Core design: dual-homed Kali (two NICs)

To meet "lab traffic on the dedicated network" **and** "internet for OmniRoute stays separate," the Kali VM needs **two network adapters**:

```
                         ┌─────────────────────────── Kali VM (attacker) ───────────────────────────┐
  Internet (hotspot) ──► │ Adapter 1 = eth0  →  VMware NAT (vmnet8)   →  default route → AI/OmniRoute │
                         │ Adapter 2 = eth1  →  VMware BRIDGED to the dedicated lab NIC               │ ──► Lab network ──► Windows target
                         └──────────────────────────────────────────────────────────────────────────┘
```

- **eth0 (existing)** → keep on **NAT** → carries **internet only** (OmniRoute → AI provider via the hotspot). Holds the **default route**.
- **eth1 (new, owner adds in VMware)** → **Bridged** to a **dedicated host interface** (a spare Ethernet port or a USB‑Ethernet dongle) → carries **lab traffic only** to the Windows target. **No default route on this side.**

Because only the lab subnet routes via eth1 and only the default (internet) routes via eth0, **lab and internet traffic never mix**. OmniRoute's upstream calls egress eth0; Hydra/Locust/NetExec/Nmap to the target egress eth1.

---

## 3. Topology options compared

| Option | How | Isolation | Cost/complexity | Verdict |
|---|---|---|---|---|
| **A. Direct Ethernet (two laptops)** | Host Ethernet ↔ Windows Ethernet, one cable, static IPs, no router. VMware bridges eth1 to the host Ethernet. | **Strongest** — only the two machines on the link, no WAN at all | Lowest (1 cable; USB‑Ethernet dongle if a laptop lacks a port) | **RECOMMENDED** for a 2-node lab |
| **B. Dedicated switch** | Both Ethernets → a small unmanaged switch (no WAN uplink). VMware bridges eth1 to the host Ethernet. | Strong — isolated L2, room to add nodes later | Low (switch + 2 cables) | Good if you'll add more lab hosts |
| **C. Travel router (LAN-only, no WAN)** | A cheap router providing a lab subnet + DHCP, **WAN port unplugged**. | Strong if WAN stays disconnected | Low–medium (router + cables) | Good if you want DHCP/services; risk = someone plugs in WAN |
| **D. VMware host-only vmnet** | A VMware host-only network. | Isolates Kali↔host only | Lowest | **UNSUITABLE** — a *separate physical* Windows laptop cannot join a VMware host-only vmnet; it only connects VMs to the host |

**Recommendation: Option A (direct Ethernet)** for a clean two-node lab — maximal isolation, minimal hardware, and the Windows target has no path to the internet at all. Use **B/C** only if you need more nodes or DHCP.

---

## 4. Required hardware (owner side)

- **Ethernet on both ends:** the attacker **host laptop** and the **Windows laptop** each need an Ethernet port. If either lacks one, a **USB‑to‑Ethernet dongle** for that machine.
- **One Ethernet cable** (modern NICs are auto‑MDIX, so a normal straight cable works for a direct link) — or a **small unmanaged switch + two cables** (Option B), or a **travel router + cables** (Option C).
- The attacker host's **lab Ethernet must be free for VMware to bridge** eth1 to it — the host's **internet stays on Wi‑Fi/hotspot**, so the Ethernet is dedicated to the lab.

No hardware changes are needed inside the Kali VM beyond adding the second VMware adapter (owner does this in VMware).

---

## 5. Addressing plan (static, no internet on the lab side)

| Host | Interface | Address | Notes |
|---|---|---|---|
| Kali (attacker) | eth0 (NAT) | `192.168.176.131/24` (DHCP, existing) | internet / OmniRoute; default route |
| Kali (attacker) | **eth1 (lab, bridged)** | **`10.10.10.10/24`** (static) | **no gateway on this interface** |
| Windows (target) | lab Ethernet | **`10.10.10.20/24`** (static) | **no default gateway**; Wi‑Fi OFF during labs |
| (Optional) lab router | LAN | `10.10.10.1/24` | only if Option C; WAN disconnected |

Lab subnet `10.10.10.0/24` is arbitrary (any unused RFC1918 range not overlapping `192.168.176.0/24`). **Static IPs** avoid any DHCP dependency for a direct link.

---

## 6. Routing design (on Kali, after the owner adds eth1)

- Keep the **default route via eth0** (NAT) → all internet / OmniRoute traffic.
- Add a **connected route for `10.10.10.0/24` via eth1** (automatic when eth1 has `10.10.10.10/24`).
- **Do NOT add a default route on eth1.** This guarantees the target subnet is reachable only over the lab NIC, and the target has no route to the internet.
- Result: `ip route get 10.10.10.20` → via **eth1**; `ip route get <any internet IP>` → via **eth0**. Clean split; no leakage.

**Fail-closed principle (to be enforced in the future Network subsystem):** if eth1 (the approved lab path) is down, lab operations must **stop and report** — never silently fall back to routing target traffic via eth0/NAT.

---

## 7. Source-IP attribution — how it will be verified (measured vs inferred)

Over this design the target sees Kali's source as **`10.10.10.10`** (the lab NIC). To **verify (measured, not inferred):**
- **On Kali:** `ip route get <target>` (confirms egress eth1) + `sudo tcpdump -i eth1 host <target>` during an approved operation (confirms packets actually leave eth1 with src `10.10.10.10`).
- **On the target (best evidence):** the Windows firewall log / `netstat -n` / Event log / a simple listener showing the **observed source address** of the inbound connection.
- **On the lab router/switch (Option B/C):** ARP/MAC and (if managed) flow records.
- "Inferred" = assuming the source from config; "measured" = a capture or target-side log proving it. The future IP‑Telemetry Manager will record which it is, with an evidence-confidence field.

---

## 8. Keeping internet (OmniRoute) separate from lab traffic

- OmniRoute (when installed) binds **loopback on Kali**; its **upstream provider calls follow the default route = eth0 = NAT = hotspot internet**.
- Lab module traffic (Hydra/Locust/NetExec/Nmap) targets `10.10.10.0/24` → **eth1 only**.
- The two paths are separated by routing (only the lab subnet via eth1; everything else via eth0). Add a guard in the Network subsystem: assert no default route via eth1, and assert the target IP resolves to the eth1 path before any operation (else fail closed).

---

## 9. Verification procedure (read-only; to run **after** the owner configures, with approval — not now)

1. `ip -br addr` → shows **eth0** (`192.168.176.x`, NAT) **and eth1** (`10.10.10.10`, lab).
2. `ip route` → `default via 192.168.176.2 dev eth0` **and** `10.10.10.0/24 dev eth1`; **no** default via eth1.
3. `ip route get 10.10.10.20` → `dev eth1`; `ip route get 1.1.1.1` → `dev eth0`.
4. (Approved reachability test, later) `ping -I eth1 10.10.10.20`; `tcpdump -i eth1` confirms egress.
5. Target isolation: on Windows, confirm **no default gateway** / Wi‑Fi off ⇒ no internet path.
6. Source-IP: on the target, observe inbound source = `10.10.10.10` (measured).

---

## 10. Owner action items (host/VMware/Windows — I will NOT change these automatically)

1. Choose a topology (recommend **A — direct Ethernet**, or **B — switch** if expanding).
2. Ensure a **dedicated Ethernet** (or USB‑Ethernet dongle) is free on the attacker host for the lab.
3. In **VMware → Virtual Network Editor**: create/confirm a **Bridged** vmnet mapped to that lab Ethernet; **add a 2nd network adapter** to the Kali VM on that bridged vmnet.
4. On **Kali**: assign `eth1 = 10.10.10.10/24` **static, no gateway** (via NetworkManager).
5. On **Windows**: set the lab Ethernet to `10.10.10.20/24`, **no gateway**, **Wi‑Fi off** during labs.
6. Tell me the final lab subnet + target IP so the Safety Gateway / blackbox / module allowlists can be configured to that authorized target.

---

## 11. Conclusion

A **dual-homed Kali (NAT NIC for internet + bridged NIC for an isolated lab Ethernet)** cleanly satisfies all goals: dedicated lab path, internet kept separate for OmniRoute, and no target exposure to external networks. **Recommended topology: direct Ethernet (Option A)** for a two-node lab. The only hardware needed is a spare Ethernet port (or a USB dongle) + a cable. **Feasibility: FEASIBLE** — pending the owner's host-side configuration, which I will not perform automatically.

**Status: feasibility report delivered. Awaiting owner approval before any configuration. No source changed, no settings changed, no live testing.**
