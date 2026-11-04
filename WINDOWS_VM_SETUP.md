# VAJRAPRAHAAR — Windows VM Setup Guide

Fresh Windows VM pe is repo ko zero se chalane ke liye step-by-step guide.
Ye ek **isolated lab console** hai (host-only network ke liye) — ise kabhi
internet-facing mat banana.

Teen tarike hai. Apni zaroorat ke hisaab se **ek** chuno:

| Route | Kab use karo | Telemetry |
|-------|--------------|-----------|
| **A — All-in-Docker** | Sabse aasaan. Demo / review ke liye. | VM ki real telemetry nahi milti (backend container ke andar chalta hai) |
| **B — Hybrid (recommended)** | Backend natively Windows pe, dashboard Docker me. VM ki **real telemetry** chahiye. | Real (local) |
| **C — Full bare-metal** | Docker nahi chahiye. | Real (local) |

---

## 0. VM prerequisites (sabse pehle)

Ye ek **target/lab VM** hai. Setup se pehle:

- **Windows 10/11 x64** VM (VirtualBox / VMware / Hyper-V).
- Network adapter ko **Host-Only** ya **Internal** rakho — bridged/NAT se
  internet-facing mat karo.
- VM ka ek **snapshot** le lo setup se pehle (rollback ke liye).
- Admin PowerShell access.

Jo tools chahiye honge (route ke hisaab se neeche install karenge):

- **Git** — <https://git-scm.com/download/win>
- **Python 3.11+** (3.13 bhi chalega) — <https://www.python.org/downloads/windows/>
  → install karte waqt **"Add python.exe to PATH"** zaroor tick karo.
- **Node.js 20 LTS** (npm ke saath) — <https://nodejs.org/>
- **Docker Desktop** (sirf Route A / B ke liye) — <https://www.docker.com/products/docker-desktop/>

Verify (PowerShell me):

```powershell
git --version
python --version
node --version
npm --version
docker --version   # sirf A/B ke liye
```

---

## 1. Repo ko VM pe laao

Do options:

**(a) Git clone** (agar repo kisi remote pe hai):

```powershell
cd $HOME\Desktop
git clone <YOUR_REPO_URL> Red_Team_Chakravyuh
cd Red_Team_Chakravyuh\red-team-chakravyuh
```

**(b) Copy/zip** — pura `red-team-chakravyuh` folder VM me copy karke
us folder ke andar PowerShell khol lo.

> ⚠️ `.env`, `.venv`, `node_modules`, `dist` — ye gitignored hai. Agar zip copy
> kar rahe ho to in folders ko **mat** copy karo (purani machine ki files VM pe
> break ho jayengi). Fresh VM pe inhe neeche dobara banayenge.

Aage ke saare commands repo root (`...\red-team-chakravyuh`) se chalengе
jab tak alag se na bola jaaye.

---

## Route A — All-in-Docker (sabse aasaan)

Docker Desktop chalu hona chahiye (taskbar me whale icon green).

```powershell
# 1. Root ka .env — Postgres password set karo
Copy-Item .env.example .env
notepad .env        # POSTGRES_PASSWORD=<kuch_strong_password> set karke save

# 2. Backend ka .env — AI key + telemetry source
Copy-Item backend\.env.example backend\.env
notepad backend\.env
#   OPENROUTER_API_KEY=<apni-openrouter-key>   (khaali chhoda to LLM "unavailable" dikhega, crash nahi)
#   TELEMETRY_SOURCE=none                       (Docker me real telemetry nahi milti)

# 3. Hybrid override file hatao (warna wo host backend dhoondhega)
Rename-Item docker-compose.override.yml docker-compose.override.yml.bak

# 4. Build + run
docker compose up -d --build
```

Dashboard khulega 👉 **http://localhost:8080**

Band karne ke liye: `docker compose down` (data rakhne ke liye volume rehta hai).

---

## Route B — Hybrid (real telemetry, recommended)

Backend **natively Windows host** pe chalta hai (taaki VM ki asli telemetry
padh sake), dashboard Docker ke nginx se serve hota hai. `docker-compose.override.yml`
automatically nginx ko `host.docker.internal:8077` pe point kar deta hai.

### B1. Backend natively chalao

```powershell
cd backend

# Virtual env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
#   Agar "running scripts is disabled" error aaye:
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned   (ek baar)

# Dependencies
pip install -r requirements.txt

# Windows target pe real telemetry ke liye (optional but recommended):
pip install pywin32==308

# Config
Copy-Item .env.example .env
notepad .env
#   TELEMETRY_SOURCE=local          <-- ye VM ki apni machine padhega
#   OPENROUTER_API_KEY=<key>        <-- AI decisions ke liye (khaali = unavailable)
#   DATABASE_URL=sqlite:///./dev.db (single-user demo ke liye theek hai)

# Run (is terminal ko khula chhodo)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8077
```

Backend chal gaya: <http://localhost:8077/api/health> pe `ok` aana chahiye.

### B2. Dashboard Docker se chalao

**Dusre** PowerShell me, repo root se:

```powershell
Copy-Item .env.example .env
notepad .env                 # POSTGRES_PASSWORD set karo
docker compose up -d --build frontend
```

`docker-compose.override.yml` file **present** honi chahiye (Route A me jo rename
kiya tha agar — yaha wapas `docker-compose.override.yml` naam rakho).

Dashboard 👉 **http://localhost:8080** (ab ye tumhare host backend se baat karega)

---

## Route C — Full bare-metal (Docker ke bina)

Do terminal chahiye.

### C1. Backend (terminal 1)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pywin32==308            # real local telemetry ke liye
Copy-Item .env.example .env
notepad .env                        # TELEMETRY_SOURCE=local, OPENROUTER_API_KEY=<key>
uvicorn app.main:app --reload --port 8077
```

### C2. Frontend (terminal 2)

```powershell
cd frontend
npm install
npm run dev                         # http://localhost:5173
```

Vite dev server `/api` aur `/ws` ko apne aap `:8077` pe proxy kar deta hai.
Dashboard 👉 **http://localhost:5173**

---

## 2. Verify sab chal raha hai

1. Dashboard khulta hai (8080 ya 5173).
2. Backend health: <http://localhost:8077/api/health> → `{"status":"ok"}`
3. Telemetry: dashboard pe **REAL LAB TELEMETRY** panel me CPU/RAM aa raha ho
   (agar `TELEMETRY_SOURCE=local` + pywin32 installed hai).
4. Integrations page khulta hai → har tool `available` ya honest `unavailable`
   (reason ke saath) dikhata hai. Ye normal hai.

**Kill switch:** header ka button ya **Win+Alt+K** (fallback **Ctrl+Alt+K**) —
range halt kar deta hai; re-arm karne tak nayi sessions refuse hongi.

---

## 3. Optional integrations (sirf jab chahiye)

Core console in sab ke bina chalta hai. Jo arm karna ho wahi install karo —
`backend\.env` me keys bharke:

- **CALDERA analyzer** — koi extra dep nahi (OpenRouter key reuse karta hai).
  Sample reports already vendored hai.
- **Locust (real DDoS driver)** — fail-closed. `pip install locust==2.32.4`,
  phir `.env` me `LOCUST_ENABLED=true` + `LOCUST_FILE_PATH` + `LOCUST_TARGET_URL`
  (authorized lab host) set karo. Users/rate/duration config se hard-capped hai.
- **vervet (Rust CLI)** — Rust toolchain chahiye: `cargo build --release -p vervet-cli`,
  phir `.env` me `VERVET_BIN=<path>`. Read-only `describe` only.
- **PentestGPT** — `pip install -e ..\PentestGPT-main\PentestGPT-main\pentestgpt_agent`,
  phir `.env` me `PENTESTGPT_CMD`. Engagement hamesha deliberate CLI action rehta hai.

---

## 4. Common dikkatein (troubleshooting)

| Problem | Fix |
|---------|-----|
| `Activate.ps1 ... running scripts is disabled` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (ek baar) |
| `POSTGRES_PASSWORD` error on `docker compose up` | Root `.env` me `POSTGRES_PASSWORD=` khaali hai — set karo |
| Dashboard khulta hai par data nahi | Backend chal raha? `http://localhost:8077/api/health` check karo |
| Telemetry `unavailable` | `TELEMETRY_SOURCE=local` set hai? `pip install pywin32` kiya? Backend restart |
| LLM `llm_unavailable` | `OPENROUTER_API_KEY` khaali hai ya galat — `backend\.env` me set karo |
| Hybrid me 8080 par 502 | Host backend band hai, ya override file missing. Backend start karo + `docker-compose.override.yml` present rakho |
| Port already in use | Koi aur process 8077/8080/5173 pe hai — band karo ya port badlo |

---

## 5. Security reminders (zaroori)

- Ye lab console **isolated, host-only network** ke liye hai — internet pe
  mat expose karo.
- `.env` aur `backend\.env` me **real keys** hoti hai — kabhi commit mat karo
  (dono already `.gitignore` me hai).
- Har module ka `execute()` **stub** hai — koi real traffic/credentials/implant
  yaha se originate nahi hota. Orchestrator sirf real telemetry padh ke reason
  karta hai aur execution ko authorized lab adapter pe defer karta hai.
- Sirf un VMs/targets ke against chalao jinke liye **tumhare paas authorization
  hai**.

---

Aur detail ke liye: root `README.md` aur `backend\README.md` dekho.
