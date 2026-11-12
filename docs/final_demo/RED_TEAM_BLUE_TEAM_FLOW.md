# CYBER CHAKRAVYUH — Red Team vs Blue Team Flow

## Roles
- **Red Team (this platform):** discovery, explicit target selection/authorization, approved bounded module execution, detectable activity generation, telemetry-producing operations.
- **Blue Team (external SOC):** Wazuh/SIEM monitoring on the **target** side — event collection, detection rules, alerting, investigation. **CHAKRAVYUH contains NO Wazuh/SIEM forwarding code** (verified: no `wazuh/syslog/siem/forward` integration in `backend/app`). Blue-Team detection therefore happens on the target's own stack and is **external** to this project.

## Event-flow table
| Red Team activity | Generated evidence | Blue Team destination | Verification status |
|---|---|---|---|
| Recon probe (`/api/telemetry/probe`) | TCP connection attempts from Kali → target ports | Target firewall/NIDS/Windows WFP (if auditing on) | **Live-generated**; SOC detection **external, not in-code** |
| SOC-activity bruteforce signature | failed SMB logins (bogus users) → **Windows 4625** | Target Windows Security log → Wazuh agent (if installed) | **Live-generated** (when target online); detection external |
| SOC-activity ddos signature | bounded TCP connection burst | NIDS (Suricata/Zeek) if deployed | **Live-generated**; detection external |
| NetExec read-only op | SMB auth/session events | Windows Security log → Wazuh | **Blocked** (target offline) |
| Internal DDoS simulation | synthetic metrics only | — (local, no traffic) | **Simulation only — no Blue-Team evidence** |
| Audit record | SQLite `AuditRecord` (local) | CHAKRAVYUH dashboard | **Live (local)** |

## What must happen for a Red action to become a Blue alert
1. Target **online** and reachable (tailnet). 2. A **Wazuh agent installed + enrolled** on the target (or a network sensor). 3. Relevant **audit policy on** (e.g., failed-logon auditing for 4625; WFP connection auditing for connection events). 4. A Wazuh **rule** matching the event (e.g., multiple-logon-failure rule). Only then does the activity surface as a Blue-Team alert. **Do not claim Wazuh receives events without this chain established.**
