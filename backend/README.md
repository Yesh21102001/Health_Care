# HealthAI Backend (FastAPI + MongoDB)

The HealthAI API. The user app (`../frontend`) and admin app (`../admin`) call it.

## Setup (Windows, PowerShell)

Requires Python 3.12+ (developed on 3.14).

```powershell
cd C:\projects\Health_care\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # your prompt now starts with (.venv)
pip install -r requirements-dev.txt
copy .env.example .env                # then edit .env (see below)
```

If `Activate.ps1` is blocked, run once:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### `.env`
- `MONGODB_URI`: your MongoDB Atlas connection string (Atlas → Database → Connect → Drivers).
- `FRONTEND_URL` / `ADMIN_URL`: the browser origins allowed to call the API.

## Run

```powershell
uvicorn app.main:app --reload --port 8000 --no-server-header
```

- Health check: http://localhost:8000/api/health
- Interactive API docs (development only): http://localhost:8000/docs

## Test

```powershell
pytest
```

Tests start their own throwaway MongoDB (downloaded on the first run), so they
don't touch your Atlas database. To use an existing MongoDB instead, set
`TEST_MONGODB_URI`.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | Database connectivity check |
| POST | `/api/auth/register` | Creates account + session cookie |
| POST | `/api/auth/login` | Session cookie on success |
| POST | `/api/auth/logout` | Revokes the session |
| GET | `/api/auth/me` | Current user, or 401 |
| POST | `/api/auth/forgot-password` | Same response whether or not the email exists |
| POST | `/api/auth/reset-password` | Single-use token; signs out all sessions |
| POST | `/api/chat` | Send a message (`conversationId` optional). Safety screen → Claude → output filter |
| GET | `/api/conversations?q=` | The user's conversations |
| GET/DELETE | `/api/conversations/{id}` | One conversation (own only) / delete it and its report |
| POST | `/api/assessment` | Generate the report for a conversation |
| GET | `/api/assessment/{id}`, `/api/assessments` | Reports (own only) |
| GET/PUT/DELETE | `/api/profile` | Profile; update; delete account (needs password) |
| POST | `/api/profile/password` | Change password (signs out other devices) |
| PUT | `/api/profile/privacy` | Health-data consent + retention (withdrawing deletes health data) |
| GET | `/api/admin/dashboard`, `/api/admin/users`, `/api/admin/audit` | Admin only; no health content |
| PATCH | `/api/admin/users/{id}` | Change role (audited) |

Create the first admin: `python -m app.cli make-admin you@example.com`

Errors always look like `{"error": "...", "fieldErrors": {"field": "message"}}`.

## Security notes
- Passwords: scrypt (N=2^17, r=8, p=1). Sessions: random token in an HttpOnly
  SameSite=Lax cookie; only its SHA-256 hash is stored.
- State-changing requests must come from an allowed Origin and be JSON (CSRF).
- Rate limits are stored in MongoDB so they hold across server instances.
- Logs contain event names and IDs only: no emails, passwords, tokens or health data.
- **Email is not connected.** In development the reset link is printed to the
  terminal; in production nothing is sent until a provider is added in
  `app/services/mailer.py`.

## Layout

```
app/
  main.py            app factory, middleware, routers
  core/              settings, password/token security, logging
  db/mongo.py        connection + indexes
  schemas/           request/response validation (Pydantic)
  services/          business logic (auth, sessions, rate limits, mail)
  api/               routes, dependencies, middleware, error format
tests/               pytest suite
```
