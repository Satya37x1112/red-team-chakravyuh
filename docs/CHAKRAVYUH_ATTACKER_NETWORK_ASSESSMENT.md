# CYBER CHAKRAVYUH — Attacker Machine Network Assessment (Phase 1)

**Author:** Claude Code (Linux network engineer / lab infra) — READ-ONLY assessment
**Date:** 2026-11-08
**Scope:** attacker side only (Kali-in-VMware). Windows target NOT required or contacted. **No configuration changed, no packages installed, no scans, no target contact, no CHAKRAVYUH code touched.**

Result legend: `VERIFIED` · `PARTIALLY VERIFIED` · `NOT VERIFIED` · `NOT ACCESSIBLE FROM GUEST`.

---

## 1. Assessment date & environment
- 2026-11-08. Physical attacker laptop → Kali Linux in **VMware Workstation** → internet via **mobile hotspot** → VMware **NAT**.
- Existing CHAKRAVYUH backend (`:8077`) + frontend (`:5173`) untouched and running.

## 2. Physical host information — **NOT ACCESSIBLE FROM GUEST**
A VM cannot reliably enumerate the physical host's interfaces. The following require **host-side** inspection by the owner (e.g. on the host OS: `ip a`/`ipconfig`, `ip r`/`route print`):
- Host OS, host **Wi-Fi interface name**, host **hotspot IPv4**, subnet mask, host default gateway, host DNS. — **NOT ACCESSIBLE FROM GUEST.**
- `open-vm-tools` is present in the guest (VMware integration confirmed), but it does not expose the host's NIC inventory.

## 3. Kali interface inventory — **VERIFIED**
```
lo     UNKNOWN  127.0.0.1/8 ::1/128
eth0   UP       192.168.176.131/24  fe80::f9a2:1b5a:41fa:572d/64
```
- Active interface: **`eth0`** (single virtual NIC; only `lo` besides it).
- MAC: **`00:0c:29:b4:30:b3`** → OUI `00:0c:29` = **VMware** (guest vNIC). NIC model: Intel 82545EM = VMware **e1000**.
- IPv4: `192.168.176.131/24`. IPv6: link-local only (`fe80::…`); **no global IPv6**.

## 4. Kali IP configuration — **VERIFIED**
- Address `192.168.176.131/24` (DHCP, via NetworkManager "Wired connection 1").
- DNS nameserver: `192.168.176.2` (the VMware NAT device also serves DNS).

## 5. Routing table — **VERIFIED**
```
default via 192.168.176.2 dev eth0 proto dhcp src 192.168.176.131 metric 100
192.168.176.0/24 dev eth0 proto kernel scope link src 192.168.176.131 metric 100
ip route get 1.1.1.1 → 1.1.1.1 via 192.168.176.2 dev eth0 src 192.168.176.131
```
- Outgoing interface for all traffic: **`eth0`**. Single default route. No second NIC, no policy routing.

## 6. Default gateway — **VERIFIED**
- `192.168.176.2`, reachable; neighbor MAC **`00:50:56:e0:7a:32`** → OUI `00:50:56` = **VMware** (vmnet device).

## 7. NAT assessment — **PARTIALLY VERIFIED (strongly consistent with VMware NAT)**
Guest-side evidence all points to **VMware NAT (vmnet8):**
- Gateway `192.168.176.2` is the classic `vmnet8` NAT gateway address (`.2`).
- Gateway MAC OUI `00:50:56` = a **VMware virtual device**, not a real hotspot router — a *bridged* setup would instead show the **hotspot router's** real MAC. This is the strongest single indicator of NAT (not bridged).
- `/24` private subnet `192.168.176.0/24`, DNS served by the same `.2` device.
- Single vNIC, DHCP from the VMware device.

**Why not fully VERIFIED:** the definitive proof (adapter set to "NAT" vs "Bridged/custom") is a **host-side VMware Virtual Network Editor** setting, not readable from the guest. Per the instruction, NAT is **not claimed as fully verified from the IP alone** — but the combined evidence (VMware gateway MAC + `.2` gateway + `/24`) is **strongly consistent with NAT**.

## 8. Internet connectivity — **VERIFIED**
```
ping -c 4 1.1.1.1  →  4/4 received, 0% loss, rtt ~61–90 ms (avg ~70 ms)
curl -I https://github.com  →  HTTP/2 200
```
Internet works through the hotspot via NAT. Latency ~70 ms is consistent with a mobile hotspot.

## 9. DNS connectivity — **VERIFIED**
```
getent hosts github.com  →  20.207.73.82 github.com
```
DNS resolution works (via `192.168.176.2`).

## 10. OmniRoute network readiness — **VERIFIED (connectivity only; nothing installed)**
```
curl -I https://registry.npmjs.org/  →  HTTP/2 200
```
- Outbound HTTPS + DNS + npm registry are reachable → the environment **can** later download/install OmniRoute (Node/npm app) and reach AI providers. **No install or LLM-config change was performed** (out of scope for this phase).

## 11. Missing information requiring physical-host inspection
- Host Wi-Fi interface name + the **host's hotspot IPv4** (the address the target would observe under NAT). — NOT ACCESSIBLE FROM GUEST.
- Host default gateway / DNS as the hotspot assigns them.
- Definitive VMware adapter mode (NAT vs bridged) from the Virtual Network Editor.
- Whether the hotspot enforces **client isolation** (determines if the host can reach a future target) — host/phone-side.

## 12. Recommended next steps
1. **Host-side baseline (owner, read-only):** on the physical laptop, record the Wi-Fi interface, hotspot IPv4, gateway, DNS; confirm the VMware adapter is NAT in the Virtual Network Editor.
2. When a target is introduced: verify hotspot **client isolation** (host → target ping) before any lab work.
3. Keep NAT as the baseline (see `CHAKRAVYUH_NETWORK_ISOLATION_ARCHITECTURE.md` §12). No guest network change is needed now.
4. Independent dev (no target needed) may proceed: generic LLM provider config, read-only network-inventory API/page.

---

### Summary table
| Item | Status |
|---|---|
| Kali interfaces / IP / routes / gateway | **VERIFIED** |
| Outgoing interface = eth0 | **VERIFIED** |
| VMware NAT | **PARTIALLY VERIFIED** (strongly consistent; host-side confirmation pending) |
| Internet connectivity | **VERIFIED** |
| DNS | **VERIFIED** |
| OmniRoute download reachability | **VERIFIED** (nothing installed) |
| Physical host Wi-Fi / hotspot IP | **NOT ACCESSIBLE FROM GUEST** |

**No network configuration was changed. No secrets exposed. Awaiting owner approval before any configuration.**
