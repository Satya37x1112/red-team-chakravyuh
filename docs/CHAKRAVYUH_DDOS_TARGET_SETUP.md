# CHAKRAVYUH — DDoS Research Target VM Setup (Design)

**Date:** 2026-11-09 · Status: **DESIGN — no VM created or booted.** Owner performs the VM steps.
This is a dedicated, disposable Linux HTTP target for bounded, authorized load research. It is
**separate** from the Windows target `100.80.167.51` (which stays untouched).

---

## 1. Recommended target OS
**Alpine Linux 3.21 (virt image)** — recommended. Rationale: idles at ~30–50 MB RAM, boots in
seconds, `python3` available via `apk`, no unnecessary services. Zero external deps needed for the
research app.
- **Alternative:** Debian 13 "trixie" netinst, "standard system utilities" only (heavier: ~250 MB RAM).

Avoid full desktops/server bundles — the host is RAM-constrained (see §3).

## 2. VM resources (sized for a constrained host)
Observed: Kali guest has only 3.8 GB RAM (~1.1 GB free); the prior host error was
*"Could not create anonymous paging file for 4096 MB: Insufficient system resources."* So keep the
new VM **small** and do **not** change the Windows target's or Kali's allocation.

| Resource | Recommended | Hard ceiling |
|---|---|---|
| RAM | **512 MB** (Alpine) | 768 MB — never 4096 MB |
| vCPU | **1** | 2 |
| Disk | **4 GB** (Alpine) / 8 GB (Debian) | 10 GB |
| Firmware | BIOS | — |

> Owner action: before creating it, check the **physical Windows host** RAM/free disk in Task Manager
> (the guest cannot see host totals). Only create the VM if the host has ≥1 GB free beyond current use.

## 3. VMware (owner actions — do NOT change adapters without approval)
1. Create VM: Alpine 3.21 virt ISO, 512 MB RAM, 1 vCPU, 4 GB disk.
2. **Snapshot "clean"** immediately after install — the VM is disposable; revert to recover.
3. Network adapter: **Bridged** (same as the working setup) OR NAT — Tailscale (§4) gives the
   reachable identity regardless, so bridging is optional.

## 4. Tailscale identity (own node; do not change existing ACLs)
On the target VM:
```sh
# Alpine:
apk add tailscale && rc-service tailscaled start && rc-update add tailscaled
tailscale up            # prints a login URL — approve on the SAME tailnet as kali
tailscale ip -4         # the target's own 100.x identity → use this in LOCUST_TARGET_URL
```
- The target gets its **own** `100.x` identity, separate from `opensoc-windows`.
- **Expose only the research port** to the tailnet peer with the target's local firewall, e.g. Alpine:
  ```sh
  apk add iptables
  iptables -A INPUT -i tailscale0 -p tcp --dport 8080 -s 100.80.154.42 -j ACCEPT   # kali only
  iptables -A INPUT -i tailscale0 -p tcp --dport 8080 -j DROP
  ```
- Do **not** enable Funnel/exit-node; do **not** modify tailnet ACLs.

## 5. HTTP research service
Copy **`backend/tools/research_target_app.py`** (zero-dependency, stdlib-only) to the target and run:
```sh
RESEARCH_HOST=0.0.0.0 RESEARCH_PORT=8080 python3 research_target_app.py
# (optional) Alpine OpenRC service for auto-restart / recovery — see the research-lab doc.
```
Endpoints (all GET, read-only): `/health`, `/test`, `/metrics` (counters + p50/p95/p99 + CPU/mem from
/proc), `/`. No writes, no admin, no shell, no intentional vulnerability. Validated on loopback here.

## 6. Recovery procedure
- Service is single-process; restart with the service manager (or re-run the command).
- `/metrics` shows CPU/mem + recovery (latency returns to baseline after load stops).
- The VM is **disposable**: `vmrun` revert to the "clean" snapshot wipes any state.

## 7. Known limitations
- Guest cannot read physical-host RAM — owner confirms host headroom before creating the VM.
- CPU% from `/proc/stat` is Linux-only (fine for Alpine/Debian).
- The app is intentionally benign — no exploitable surface to "attack" beyond load/availability.
