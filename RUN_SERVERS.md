# VAJRAPRAHAAR — Servers Start Karne Ki Guide (Local Dev)

Do server hain. Dono alag terminal mein chalte hain:

| Server | Kya hai | URL |
|--------|---------|-----|
| **Backend** | FastAPI (telemetry, AI engine, integrations, WebSocket) | http://127.0.0.1:8077 |
| **Frontend** | React + Vite dashboard (`/api` + `/ws` ko backend pe proxy karta hai) | http://localhost:5173 |

> Vite dev server apne aap `/api` aur `/ws` ko `:8077` pe forward karta hai — isliye bas dono chalu hone chahiye, aur kuch wiring nahi.

Demo/presentation ke liye do **optional** targets bhi hain — DDoS demo site (`:3000`)
aur brute-force SSH target (`:5000`). Inhe chalane ke liye **section 3** dekho.

---

## 1. Backend server

**Terminal 1** — repo root se:

```powershell
cd backend

# Pehli baar: virtual env + dependencies
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pywin32==308          # real local telemetry ke liye (Windows)

# Config (pehli baar): .env banao aur keys/target bharo
Copy-Item .env.example .env
notepad .env                      # OPENROUTER_API_KEY, TELEMETRY_SOURCE=local, etc.

# Server chalu karo (is terminal ko khula chhodo)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8077
```

Ready hone par ye dikhega:

```
INFO:     Uvicorn running on http://127.0.0.1:8077 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

Verify: browser mein <http://127.0.0.1:8077/api/health> → `{"status":"ok", ...}`

> **Dhyaan:** `.env` badalne ke baad backend **restart** karna padta hai (settings startup pe load hoti hain). `--reload` sirf `.py` files watch karta hai, `.env` nahi.

---

## 2. Frontend server

**Terminal 2** — repo root se:

```powershell
cd frontend

npm install        # pehli baar (ya package.json badle to)
npm run dev        # http://localhost:5173
```

Ready hone par:

```
VITE v5.x  ready in ... ms
➜  Local:   http://localhost:5173/
```

Browser mein kholo 👉 **http://localhost:5173**

---

## 3. Demo targets — DDoS site (:3000) aur Brute-force SSH (:5000)

Ye **optional** hain — sirf demo/presentation ke liye. Core console (backend +
frontend) in ke bina bhi chalta hai. Dono **deliberately-vulnerable lab targets**
hain, sirf **localhost / isolated** — koi real system touch nahi hota.

### (a) DDoS demo site — http://localhost:3000

Ek jaan-boojhkar fragile single-threaded site, taaki DDoS panel se overwhelm hoke
"unavailable" ho jaaye. **Naya terminal**, repo root se:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -I tools\demo_site.py 3000
```

`demo site listening on http://127.0.0.1:3000` aane par UP hai. Verify:
<http://localhost:3000> → "Demo site is UP".

DDoS isi pe maarne ke liye `backend\.env` mein target set karo, phir backend restart:

```
LOCUST_TARGET_URL=http://127.0.0.1:3000
```

### (b) Brute-force SSH target — 127.0.0.1:5000  *(WSL chahiye)*

Ek deliberately-weak SSH account (`labadmin` / `Welcome1`) jise Hydra crack kar sake.
Windows pe native SSH server nahi hota, isliye ye **WSL ke andar** chalta hai.
**Naya terminal**, repo root se:

```powershell
wsl -d Ubuntu -u root bash -c "sed 's/\r$//' /mnt/c/Users/manoh/OneDrive/Desktop/Red_Team_Chakravyuh/red-team-chakravyuh/backend/tools/demo_ssh_target.sh | bash -s -- 5000 labadmin Welcome1"
```

`[+] SSH demo target UP on 127.0.0.1:5000` aane par ready. Hydra panel ke liye
`backend\.env` mein (pehle se hona chahiye), phir backend restart:

```
HYDRA_ENABLED=true
HYDRA_TARGET=127.0.0.1
HYDRA_SERVICE=ssh
HYDRA_PORT=5000
```

> **Note:** Hydra khud WSL ke andar chalta hai aur SSH target bhi WSL mein — isliye
> dono `127.0.0.1:5000` pe ek-dusre ko dikhte hain (Windows se wo port na dikhe to
> bhi theek hai). **WSL band/reboot** hone par SSH target band ho jaata hai —
> dobara upar wala command chala dena.

---

## 4. Servers band karna

- Jis terminal mein chal raha hai, usme **Ctrl+C**.
- Ya port se kill karo (PowerShell):

```powershell
# port 8077 (backend), 5173 (frontend), ya 3000 (DDoS demo) pe jo PID hai use kill karo
Get-NetTCPConnection -LocalPort 8077 -State Listen | Select-Object -Expand OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
Get-NetTCPConnection -LocalPort 5173 -State Listen | Select-Object -Expand OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
Get-NetTCPConnection -LocalPort 3000 -State Listen | Select-Object -Expand OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
```

> SSH demo target (`:5000`) WSL ke andar hai — band karne ke liye:
> `wsl -d Ubuntu -u root service ssh stop` (ya WSL hi band kar do: `wsl --shutdown`).

---

## 5. Startup order aur dependency

1. **Backend pehle** chalu karo, phir frontend.
2. Backend band hai to dashboard khulega par data/`502`-type errors aayenge. Backend wapas chalu karo + page refresh.
3. Dono independent process hain — ek ko restart karne se dusra affect nahi hota.

---

## 6. Common dikkatein

| Problem | Fix |
|---------|-----|
| `Activate.ps1 ... running scripts is disabled` | Ek baar: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `.env` badla par change nahi dikha | Backend **restart** karo (`.env` startup pe load hoti hai) |
| Frontend load nahi ho raha / white screen | Terminal 2 ka Vite log dekho — build/import error aksar waha dikhta hai |
| `port already in use` | Upar section 3 wale commands se purana process kill karo |
| Dashboard khulta hai par telemetry khali | `TELEMETRY_SOURCE=local` set hai? `pip install pywin32` kiya? Backend restart |
| Integration `unavailable` | Normal hai — uska tool/binary/key missing hai; adapter honestly batata hai, crash nahi karta |

---

## 7. Ek-line summary (jab sab setup ho chuka ho)

```powershell
# Terminal 1 — backend
cd backend;  .\.venv\Scripts\Activate.ps1;  python -m uvicorn app.main:app --host 127.0.0.1 --port 8077

# Terminal 2 — frontend
cd frontend;  npm run dev

# Terminal 3 — DDoS demo target (optional)
cd backend;  .\.venv\Scripts\Activate.ps1;  python -I tools\demo_site.py 3000

# Terminal 4 — Brute-force SSH target (optional, WSL)
wsl -d Ubuntu -u root bash -c "sed 's/\r$//' /mnt/c/Users/manoh/OneDrive/Desktop/Red_Team_Chakravyuh/red-team-chakravyuh/backend/tools/demo_ssh_target.sh | bash -s -- 5000 labadmin Welcome1"
```

Dashboard: **http://localhost:5173** · Backend health: **http://127.0.0.1:8077/api/health**
DDoS target: **http://localhost:3000** · Brute-force target: **127.0.0.1:5000** (SSH, in WSL)

---

Docker / VM par full setup ke liye: `WINDOWS_VM_SETUP.md` dekho.
