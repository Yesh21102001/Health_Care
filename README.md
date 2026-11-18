# HealthAI

An AI-assisted health information and symptom assessment platform.
**Not a medical device and not ready for real patients** - see "Before real users" below.

```
Health_care/
├── frontend/   Next.js 16 - public site + patient app           http://localhost:3000
├── admin/      Next.js 16 - admin console                        http://localhost:3001
├── backend/    Python FastAPI - API, MongoDB, Claude, safety     http://localhost:8000
└── _archive/   the earlier TypeScript auth backend (unused; safe to delete after commit)
```

Both Next.js apps forward `/api/*` to the backend, so browsers only ever talk
to one origin and the session cookie stays first-party.

## Prerequisites (Windows)
- Node.js 20+ (developed on 24) and npm
- Python 3.12+ (developed on 3.14)
- A MongoDB database - free MongoDB Atlas M0 cluster is fine
- An Anthropic API key for the AI chat (https://console.anthropic.com/ → API Keys).
  Without one everything works except the AI turns, which return a clear "not configured" error.

## First-time setup

```powershell
# 1. Backend
cd C:\projects\Health_care\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy .env.example .env        # fill in MONGODB_URI and ANTHROPIC_API_KEY

# 2. User app
cd ..\frontend
npm install
copy .env.example .env.local

# 3. Admin app
cd ..\admin
npm install
copy .env.example .env.local
```

### MongoDB Atlas
1. Create a free M0 cluster at https://www.mongodb.com/cloud/atlas.
2. Database Access → add a database user with a strong password.
3. Network Access → add your IP (for cloud hosting you may need `0.0.0.0/0`; then rely on the strong password).
4. Connect → Drivers → copy the `mongodb+srv://...` string into `backend/.env` as `MONGODB_URI`.

## Run (three terminals)

```powershell
# Terminal 1 - API
cd backend; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8000

# Terminal 2 - user app
cd frontend; npm run dev

# Terminal 3 - admin app
cd admin; npm run dev
```

### Create the first admin
There is deliberately no way to become admin through the website.
Register normally in the user app, then:

```powershell
cd backend; .\.venv\Scripts\Activate.ps1
python -m app.cli make-admin you@example.com
```

Note for local development: browsers share cookies across ports on `localhost`,
so signing in to the admin app also signs you in to the user app as that account.
In production, use separate subdomains and this doesn't happen.

## Tests

```powershell
cd backend; .\.venv\Scripts\Activate.ps1; pytest      # 87 tests, uses a throwaway MongoDB
cd frontend; npm run lint; npm run typecheck; npm run build
cd admin;    npm run lint; npm run typecheck; npm run build
```

Backend tests cover authentication, sessions, CSRF, rate limiting, chat flow,
**emergency scenarios (the AI must not be called)**, AI-output filtering,
report rules, per-user access control, privacy/consent and deletion, and admin
authorization (including that admin views contain no health content).
The AI is replaced by a fake in tests, so they cost nothing.

There are no automated browser/UI tests yet (layout, mobile responsiveness).

## How the safety design works
1. **Before the AI:** every user message is screened by deterministic rules
   (`backend/app/services/safety_service.py`). Emergency signs (chest pain with arm/jaw
   pain, breathing difficulty, stroke signs, seizures, severe bleeding, anaphylaxis,
   overdose, self-harm...) return fixed emergency guidance immediately, without calling the AI,
   and pause the conversation. "Urgent" signs set a floor the report can't go below.
2. **The AI** (Claude, `ai_service.py`) is instructed to ask one question at a time,
   never diagnose, never name medicines or doses, and to express uncertainty. Every
   response is structured JSON and validated by the server.
3. **After the AI:** replies are filtered for dosing and diagnostic certainty;
   reports are checked (no "confirmed" diagnoses, urgency floor enforced, size limits).

## Before real users (not optional)
- **Clinical review.** The red-flag rules and prompts were written by engineers, not
  clinicians. They are English-only and keyword-based: they will miss some emergencies
  and flag some non-emergencies. A qualified medical team must review, extend and test them.
- **Regulation.** Symptom-assessment software may be regulated as a medical device in
  India (CDSCO, Medical Devices Rules 2017) and elsewhere. Get regulatory advice.
- **Legal.** Privacy Policy and Terms are drafts; they need review by a lawyer
  (including India's DPDP Act, 2023).
- **Email.** Password-reset emails are not sent yet. Connect a provider in
  `backend/app/services/mailer.py`.
- **AI not tested live.** The Claude integration was built against the official SDK and
  tested with a fake; it has not been run against the real API in this project yet.
  Run a few conversations with your key before relying on it.

See `DEPLOYMENT.md` to put it online.
