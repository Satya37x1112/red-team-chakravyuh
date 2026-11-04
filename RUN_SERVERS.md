# VAJRAPRAHAAR — Servers Start Karne Ki Guide (Local Dev)

Do server hain. Dono alag terminal mein chalte hain:

| Server | Kya hai | URL |
|--------|---------|-----|
| **Backend** | FastAPI (telemetry, AI engine, integrations, WebSocket) | http://127.0.0.1:8077 |
| **Frontend** | React + Vite dashboard (`/api` + `/ws` ko backend pe proxy karta hai) | http://localhost:5173 |

> Vite dev server apne aap `/api` aur `/ws` ko `:8077` pe forward karta hai — isliye bas dono chalu hone chahiye, aur kuch wiring nahi.

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

## 3. Servers band karna

- Jis terminal mein chal raha hai, usme **Ctrl+C**.
- Ya port se kill karo (PowerShell):

```powershell
# port 8077 (backend) ya 5173 (frontend) pe jo PID hai use kill karo
Get-NetTCPConnection -LocalPort 8077 -State Listen | Select-Object -Expand OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
Get-NetTCPConnection -LocalPort 5173 -State Listen | Select-Object -Expand OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
```

---

## 4. Startup order aur dependency

1. **Backend pehle** chalu karo, phir frontend.
2. Backend band hai to dashboard khulega par data/`502`-type errors aayenge. Backend wapas chalu karo + page refresh.
3. Dono independent process hain — ek ko restart karne se dusra affect nahi hota.

---

## 5. Common dikkatein

| Problem | Fix |
|---------|-----|
| `Activate.ps1 ... running scripts is disabled` | Ek baar: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `.env` badla par change nahi dikha | Backend **restart** karo (`.env` startup pe load hoti hai) |
| Frontend load nahi ho raha / white screen | Terminal 2 ka Vite log dekho — build/import error aksar waha dikhta hai |
| `port already in use` | Upar section 3 wale commands se purana process kill karo |
| Dashboard khulta hai par telemetry khali | `TELEMETRY_SOURCE=local` set hai? `pip install pywin32` kiya? Backend restart |
| Integration `unavailable` | Normal hai — uska tool/binary/key missing hai; adapter honestly batata hai, crash nahi karta |

---

## 6. Ek-line summary (jab sab setup ho chuka ho)

```powershell
# Terminal 1
cd backend;  .\.venv\Scripts\Activate.ps1;  python -m uvicorn app.main:app --host 127.0.0.1 --port 8077

# Terminal 2
cd frontend;  npm run dev
```

Dashboard: **http://localhost:5173** · Backend health: **http://127.0.0.1:8077/api/health**

---

Docker / VM par full setup ke liye: `WINDOWS_VM_SETUP.md` dekho.
