# Deploy ClawWork to Railway in ~5 minutes

Self-host the ClawWork SaaS (Next.js + FastAPI + PostgreSQL) on [Railway](https://railway.app) with minimal steps.

## Prerequisites

- Railway account ([railway.app](https://railway.app))
- GitHub repo connected to Railway (or use Railway CLI)

## 1. Clone and prepare

```bash
git clone https://github.com/HKUDS/ClawWork.git
cd ClawWork
```

## 2. Environment variables

Create a `.env` (or set in Railway dashboard):

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string (Railway provides this if you add Postgres) |
| `NEXTAUTH_SECRET` | Yes | Random string, e.g. `openssl rand -base64 32` |
| `NEXTAUTH_URL` | Yes | Your app URL, e.g. `https://your-app.up.railway.app` |
| `GITHUB_ID` | For GitHub login | GitHub OAuth App Client ID |
| `GITHUB_SECRET` | For GitHub login | GitHub OAuth App Client Secret |
| `OPENAI_API_KEY` | For agents | OpenAI or OpenRouter API key |
| `STRIPE_SECRET_KEY` | For billing | Stripe secret key (when you add billing) |
| `STRIPE_WEBHOOK_SECRET` | For billing | Stripe webhook signing secret |

## 3. Deploy on Railway

### Option A: Railway dashboard

1. **New Project** → **Deploy from GitHub repo** (select ClawWork).
2. **Add PostgreSQL**: Project → New → Database → PostgreSQL. Copy `DATABASE_URL` into your service.
3. **Add service**: New → GitHub Repo → same repo. Root directory: repo root.
4. **Configure build**:  
   - **Builder**: Dockerfile  
   - **Dockerfile path**: `Dockerfile.web` (for the Next.js app) or use **Docker Compose** (see below).
5. Set all env vars in the service Variables tab; add `DATABASE_URL` from the Postgres service.
6. Deploy. Set **Root Directory** to `/` and **Dockerfile** to `Dockerfile.web` if you deploy only the web app.

### Option B: Docker Compose on Railway

Railway can run multiple services from one repo:

1. **New Project** → **Empty Project**.
2. **New** → **Database** → **PostgreSQL**. Note the `DATABASE_URL`.
3. **New** → **GitHub Repo** → ClawWork.  
4. In **Settings** → **Deploy**:  
   - **Root Directory**: leave empty (repo root).  
   - **Docker Compose**: enable and set path to `docker-compose.yml` (or create a `railway.compose.yml` that references the Postgres URL).
5. In practice, deploy **web** and **api** as separate services:  
   - Service 1: Dockerfile `Dockerfile.web`, env with `DATABASE_URL`, `NEXTAUTH_*`, `GITHUB_*`.  
   - Service 2: Dockerfile `Dockerfile.api`, env with `DATABASE_URL`, `OPENAI_API_KEY`, etc.
6. Link Postgres to both services via `DATABASE_URL`.

### Option C: Railway CLI

```bash
npm i -g @railway/cli
railway login
railway link  # or railway init
railway add  # add PostgreSQL
railway up   # deploy from current directory (needs Dockerfile or build config)
```

## 4. Run migrations

After first deploy, run Drizzle migrations against the Railway Postgres:

```bash
DATABASE_URL="postgresql://..." npm run db:migrate -w @clawwork/db
```

Or in Railway: add a one-off job or use **Run Command** with `npm run db:migrate -w @clawwork/db` and `DATABASE_URL` set.

## 5. Migrate existing file-based data (optional)

If you have existing `livebench/data/agent_data/` and a user in the DB:

```bash
DATABASE_URL="postgresql://..." npx tsx scripts/migrate_file_data_to_postgres.ts --default-user-id=<your-user-uuid>
```

## 6. Post-deploy

- Set **NEXTAUTH_URL** to your public URL (e.g. `https://clawwork.up.railway.app`).
- For GitHub login: create a GitHub OAuth App and set `GITHUB_ID` and `GITHUB_SECRET`.
- Open the app URL and sign in.

## One-click template (future)

A **Deploy to Railway** button can point to a template that:

1. Clones the repo.
2. Adds Postgres.
3. Deploys `Dockerfile.web` (and optionally `Dockerfile.api`) with suggested env vars.

Until then, use the steps above.

## Fly.io / Render

- **Fly.io**: `fly launch` and attach Postgres; set `DOCKERFILE` to `Dockerfile.web` or use `fly.toml` with multiple processes.
- **Render**: New Web Service from repo; use Docker and `Dockerfile.web`; add Render Postgres and set `DATABASE_URL`.

Same env vars and migration steps apply.
