# Deploying HealthAI

Recommended layout (one domain, three subdomains):

| App | Host | Example URL |
|---|---|---|
| User app (`frontend/`) | Vercel | `https://healthai.example.com` |
| Admin app (`admin/`) | Vercel (separate project) | `https://admin.healthai.example.com` |
| API (`backend/`) | Render, Railway, Fly.io or any host that runs a Python web service | `https://api.healthai.example.com` |
| Database | MongoDB Atlas | - |

Why not the API on Vercel too? It can run FastAPI, but a long-lived Python
service is simpler for a database connection pool and AI calls that can take
tens of seconds. Either works; the steps below use Render.

## 0. Before you start
- Put the whole `Health_care` folder in one Git repository on GitHub
  (one repo, three folders). Check `git status` shows **no** `.env` / `.env.local` files.
- Have ready: Atlas connection string, Anthropic API key, your domain.

## 1. Database (MongoDB Atlas)
- Use a dedicated database user for production with a long random password.
- Network Access: allow your API host's outbound IPs if it publishes them; otherwise `0.0.0.0/0`.
- Atlas encrypts data at rest and requires TLS in transit by default.
- Enable backups (paid tiers) before storing real health data.

## 2. API (Render example)
1. Render → New → Web Service → connect the GitHub repo.
2. Root directory: `backend`
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --no-server-header --proxy-headers`
5. Environment variables:

   | Key | Value |
   |---|---|
   | `ENVIRONMENT` | `production` |
   | `MONGODB_URI` | your Atlas string |
   | `MONGODB_DB` | `healthai` |
   | `FRONTEND_URL` | `https://healthai.example.com` |
   | `ADMIN_URL` | `https://admin.healthai.example.com` |
   | `TRUST_PROXY` | `true` |
   | `ANTHROPIC_API_KEY` | your key |
   | `PYTHON_VERSION` | `3.14.10` (or the version Render supports) |

6. Health check path: `/api/health`.
7. Custom domain: `api.healthai.example.com`.

In production the API docs (`/docs`) are disabled and cookies use the
`__Host-` prefix, which requires HTTPS.

## 3. User app (Vercel)
1. Vercel → Add New Project → import the repo.
2. Root Directory: `frontend`.
3. Environment variables (Production **and** Preview):
   - `BACKEND_URL` = `https://api.healthai.example.com`
   - `NEXT_PUBLIC_SITE_URL` = `https://healthai.example.com`
4. Deploy. **`BACKEND_URL` is used at build time** (it's baked into the `/api`
   rewrite). If you change it, redeploy.
5. Domains → add `healthai.example.com` and follow Vercel's DNS instructions.

## 4. Admin app (Vercel, second project)
Same as above with Root Directory `admin`, `BACKEND_URL` set the same way,
and domain `admin.healthai.example.com`. Consider also restricting it with
Vercel's password protection / trusted IPs.

## 5. After deploying
- Register your own account on the user app, then on the API host run
  `python -m app.cli make-admin you@example.com` (Render → Shell).
- Check `https://api.healthai.example.com/api/health` returns `{"status":"ok"...}`.
- Sign in to the admin app: "System health" should show Database: Connected
  and the AI model name.
- Run a full conversation, generate a report, download it as PDF, delete it.

## Security checklist
- [ ] No secrets in Git (`git log -p | findstr /i "mongodb+srv sk-ant"` returns nothing)
- [ ] `ENVIRONMENT=production` on the API
- [ ] HTTPS everywhere (Vercel and Render provide certificates)
- [ ] Strong, unique Atlas password; production DB user is not your personal login
- [ ] Email provider connected for password resets
- [ ] Clinical, legal and regulatory review completed (see README "Before real users")
- [ ] Monitoring: Render logs + Vercel logs; logs contain IDs and events only, never health content
