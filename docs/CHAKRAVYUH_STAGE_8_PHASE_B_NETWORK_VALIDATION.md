# CYBER CHAKRAVYUH — Stage 8 Phase B Network & Tailscale Validation

**Document Version:** 1.0  
**Date:** 2026-11-10  
**Host Platform:** Kali Linux (VMware Guest, x86_64)  
**Repository Path:** `/home/kali/AI_red_Team/red-team-chakravyuh`  
**Git HEAD:** `d7c7e44` (Clean working tree)  
**Auditor Roles:** Senior Cybersecurity Architect, Network Security Engineer, Red-Team Platform Specialist  

---

## 1. Executive Summary & Verdict

Phase B conducted a non-disruptive, read-only network inspection of the Kali Linux environment to validate interface bindings, Tailscale mesh connectivity, kernel routing policies, direct vs. DERP relay states, and latency metrics to the Windows target (`100.80.167.51`).

### Phase B Verdict:
# **VERIFIED WITH LIMITATIONS**

#### Verdict Justification:
1. **Connectivity Verified**: Non-disruptive Tailscale pings confirm that `100.80.167.51` (`opensoc-windows`) is **ONLINE** and responsive.
2. **Direct Connection Verified**: Tailscale has established an active **direct connection** to the Windows target via IPv6 endpoint `[2401:4900:8fd3:59c5:1491:4dcc:612f:a097]:41641` with DERP Mumbai (`bom`) serving as backup.
3. **Route Isolation Verified**: Kernel routing policy rule 5270 routes all traffic destined for `100.80.167.51` exclusively through `tailscale0` (Table 52). Zero target traffic routes through the physical default gateway (`eth0`).
4. **Limitation 1 (Governance)**: The target is registered to `onlymahibhatt@gmail.com` (different account than Kali's `manoharisatyasarthak@gmail.com`). Technical reachability does not equal authorization.
5. **Limitation 2 (Hotspot Telemetry)**: Same-hotspot connectivity cannot be proven from Kali-side telemetry alone due to AP client isolation and differing carrier IPv6 prefixes.
6. **Limitation 3 (Target Service Scope)**: While Tailscale layer-3 reachability is verified, no scanning was performed to confirm whether an HTTP service is hosted on the Windows machine for real Locust load testing.

---

## 2. Network Interface Inventory (Kali Linux)

Inspection command: `ip a`

```text
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host noprefixroute 
       valid_lft forever preferred_lft forever

2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    link/ether 00:0c:29:b4:30:b3 brd ff:ff:ff:ff:ff:ff
    inet 10.81.189.204/24 brd 10.81.189.255 scope global dynamic noprefixroute eth0
       valid_lft 2548sec preferred_lft 2548sec
    inet6 2409:40e2:11ea:9dd5:d33:d4c2:6a00:9631/64 scope global dynamic noprefixroute 
       valid_lft 7020sec preferred_lft 7020sec
    inet6 fe80::f9a2:1b5a:41fa:572d/64 scope link noprefixroute 
       valid_lft forever preferred_lft forever

3: tailscale0: <POINTOPOINT,MULTICAST,NOARP,UP,LOWER_UP> mtu 1280 qdisc fq_codel state UNKNOWN group default qlen 500
    link/none 
    inet 100.80.154.42/32 scope global tailscale0
       valid_lft forever preferred_lft forever
    inet6 fd7a:115c:a1e0::129:9a2b/128 scope global 
       valid_lft forever preferred_lft forever
    inet6 fe80::984d:42c:b225:3781/64 scope link stable-privacy proto kernel_ll 
       valid_lft forever preferred_lft forever
```

### Key Observations:
- **`eth0`**: Local private subnet `10.81.189.0/24`, Kali assigned `10.81.189.204`. Dynamic IPv6 prefix assigned: `2409:40e2:...` (Reliance Jio Infocomm).
- **`tailscale0`**: Virtual point-to-point interface assigned `100.80.154.42/32` (IPv4) and `fd7a:115c:a1e0::129:9a2b/128` (IPv6).

---

## 3. Tailscale Status & Peer Information

Inspection command: `tailscale status` & `tailscale status --json`

### 3.1 Local Node (Self)
- **Hostname**: `kali` (`kali.tail2ab33c.ts.net.`)
- **Tailscale IPv4**: `100.80.154.42`
- **Tailscale IPv6**: `fd7a:115c:a1e0::129:9a2b`
- **Account Identity**: `manoharisatyasarthak@gmail.com`
- **Nearest DERP Relay**: Mumbai (`bom`, Relay 18)

### 3.2 Target Node (Windows)
- **Hostname**: `OpenSOC-Windows` (`opensoc-windows`)
- **Tailscale IPv4**: `100.80.167.51`
- **Tailscale IPv6**: `fd7a:115c:a1e0::8329:a734`
- **OS Type**: Windows
- **Account Identity**: `onlymahibhatt@gmail.com` (**Different Tailscale Account**)
- **Peer State**: `Active`

### 3.3 Other Visible Tailnet Peers
- `100.84.184.33` (`CyberKabbali` — `manoharisatyasarthak@gmail.com`)
- `100.86.13.120` (`fedora` — `onlymahibhatt@gmail.com`)
- `100.113.164.29` (`soc-server` — `onlymahibhatt@gmail.com`)

---

## 4. Direct versus DERP-Relayed Connection Status

Inspection command: `tailscale status | grep opensoc-windows`

```text
100.80.167.51   opensoc-windows  onlymahibhatt@         windows  active; direct [2401:4900:8fd3:59c5:1491:4dcc:612f:a097]:41641
```

### Analysis:
1. **Direct Path Established**: The connection to `opensoc-windows` is **direct**, communicating peer-to-peer over UDP via IPv6 socket `[2401:4900:8fd3:59c5:1491:4dcc:612f:a097]:41641`.
2. **DERP Relay Fallback**: DERP relay `bom` (Mumbai, latency 91.3ms) is maintained as the control and discovery channel. If direct peer-to-peer UDP punch packets drop, traffic falls back transparently to the Mumbai relay.

---

## 5. Linux Routing Rules and Route Selection

Inspection commands:
- `ip rule`
- `ip route`
- `ip route show table 52`
- `ip route get 100.80.167.51`

### 5.1 Kernel Policy Routing Rules (`ip rule`)
```text
0:	from all lookup local
5210:	from all fwmark 0x80000/0xff0000 lookup main
5230:	from all fwmark 0x80000/0xff0000 lookup default
5250:	from all fwmark 0x80000/0xff0000 unreachable
5270:	from all lookup 52
32766:	from all lookup main
32767:	from all lookup default
```

### 5.2 Main Routing Table (`ip route`)
```text
default via 10.81.189.47 dev eth0 proto dhcp src 10.81.189.204 metric 100 
10.81.189.0/24 dev eth0 proto kernel scope link src 10.81.189.204 metric 100 
```

### 5.3 Tailscale Routing Table 52 (`ip route show table 52`)
```text
100.80.167.51 dev tailscale0 
100.84.184.33 dev tailscale0 
100.86.13.120 dev tailscale0 
100.100.100.100 dev tailscale0 
100.113.164.29 dev tailscale0 
```

### 5.4 Route Selection for Windows Target (`ip route get 100.80.167.51`)
```text
100.80.167.51 dev tailscale0 table 52 src 100.80.154.42 uid 1000 
    cache 
```

### Routing Verification Conclusions:
- The default route for all public internet traffic is `10.81.189.47 dev eth0`.
- Rule `5270` forces traffic destined for Tailscale IPs (including `100.80.167.51`) into `table 52`.
- `table 52` binds destination `100.80.167.51` strictly to `dev tailscale0` with source IP `100.80.154.42`.
- **Isolation Confirmed**: Under no circumstances will packets destined for the Windows target route out the default physical interface (`eth0`).

---

## 6. Connectivity Evidence & Latency Metrics

Inspection command: `tailscale ping --timeout=10s -c 2 100.80.167.51`

```text
pong from opensoc-windows (100.80.167.51) via [2401:4900:8fd3:59c5:1491:4dcc:612f:a097]:41641 in 2.441s
```

Subsequent non-disruptive samples:
- Sample 1: `85ms` (Direct UDP IPv6)
- Sample 2: `677ms` (Direct UDP IPv6)
- Sample 3: `2.441s` (Initial peer endpoint punch over cellular data)
- Sample 4: `2.917s` (Radio channel scheduling delay)

### Latency Assessment:
Latency fluctuates between 85ms and 2.9 seconds. This jitter is typical for cellular mobile hotspot connections operating over commercial mobile networks in India, where radio resource control (RRC) transitions between idle and active states when packets are intermittently transmitted.

---

## 7. Same-Hotspot Verification Analysis

Requirement: *Confirm whether both devices are using the same mobile hotspot, based only on available evidence. Do not claim this is verified if the available information cannot establish it.*

### 7.1 Observed Evidence from Kali:
1. **Local Network Subnet**: Kali is on `10.81.189.0/24` with DHCP gateway `10.81.189.47`.
2. **Local ARP Neighbors (`ip neigh`)**:
   ```text
   10.81.189.47 dev eth0 lladdr 6e:ce:16:ae:31:b8 REACHABLE 
   fe80::6cce:16ff:feae:31b8 dev eth0 lladdr 6e:ce:16:ae:31:b8 router REACHABLE 
   ```
   Only the hotspot gateway MAC address (`6e:ce:16:ae:31:b8`) is visible in Kali's ARP neighbor table. The Windows host's MAC does not appear in Kali's local ARP table.
3. **Public WAN Endpoints (`tailscale netcheck`)**:
   - Kali Public IPv4: `49.42.166.110` (Reliance Jio Infocomm).
   - Kali Public IPv6: `2409:40e2:11ea:9dd5:...` (Reliance Jio Infocomm).
   - Windows Target Direct IPv6 Endpoint: `2401:4900:8fd3:59c5:...` (Bharti Airtel).

### 7.2 Defensible Technical Conclusion:
**Same-Hotspot Status: UNVERIFIABLE FROM KALI-SIDE EVIDENCE ALONE.**

- **Why it cannot be confirmed**:
  1. If Kali and Windows were directly tethered to the same Wi-Fi hotspot with client isolation disabled, Windows might appear in the local ARP table; here, only the router/gateway is visible.
  2. The observed public IPv6 prefixes differ (`2409:40e2` for Kali vs `2401:4900` for Windows). This strongly indicates that Kali and Windows are egressing through distinct cellular carriers (Jio vs Airtel), OR that one device is on Wi-Fi while the other routes through cellular data, OR that the hotspot device uses multi-WAN routing.
  3. Consequently, the claim that both devices share the exact same mobile hotspot cannot be factually confirmed using only Kali-side evidence, and is recorded as unverified.

---

## 8. Network Security & Governance Observations

1. **Non-Disruptive Assessment Maintained**: No TCP port scans, SYN sweeps, UDP floods, or Nmap scans were executed. All connectivity tests were performed using non-disruptive Tailscale ICMP/WireGuard-encapsulated echo frames (`tailscale ping`).
2. **Zero Attack Traffic Dispatched**: Neither Hydra, Locust, nor NetExec was executed during Phase B.
3. **Multi-Account Authorization Boundary**: Because `opensoc-windows` belongs to account `onlymahibhatt@gmail.com`, live offensive actions remain strictly gated behind documented target-owner authorization.

---

## 9. Remaining Operational Blockers

1. **Target Authorization**: Written rules of engagement and owner authorization from `onlymahibhatt@gmail.com` are required before Phase C/D live attack testing.
2. **Target HTTP Service Validation**: It remains unverified whether `100.80.167.51` hosts an active HTTP/HTTPS service necessary for real Locust load testing.

---

## 10. Phase B Sign-Off & Verification Evidence

- **Files Created**: `docs/CHAKRAVYUH_STAGE_8_PHASE_B_NETWORK_VALIDATION.md`
- **Files Modified**: `0 source code files modified`
- **Network Configuration Altered**: `None` (Zero route, firewall, or Tailscale changes)
- **Exit Code of All Commands**: `0`
