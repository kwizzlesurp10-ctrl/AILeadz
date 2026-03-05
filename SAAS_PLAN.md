# ClawWork SaaS — Production Implementation Plan

Turn the OpenClaw AI Coworker dashboard into a self-hostable, paid SaaS ($29–$99/mo) with multi-tenant isolation, PostgreSQL, Stripe, and one-click deploy.

---

## Current State

| Layer        | Tech              | Location                    |
|-------------|-------------------|-----------------------------|
| Frontend    | Vite + React      | `frontend/`                 |
| Backend API | Python FastAPI    | `livebench/api/server.py`   |
| Data        | File-based        | `livebench/data/agent_data/{signature}/` |
| Config      | JSON + .env       | `livebench/configs/`, `.env`|

**File-based data shapes (to migrate):**

- `agent_data/{signature}/economic/balance.jsonl` — balance per date
- `agent_data/{signature}/economic/task_completions.jsonl` — task_id, date, evaluation_score, money_earned, wall_clock_seconds
- `agent_data/{signature}/economic/token_costs.jsonl` — token cost per date
- `agent_data/{signature}/activity_logs/{date}/log.jsonl` — decisions
- `agent_data/{signature}/work/tasks.jsonl`, `evaluations.jsonl`
- `agent_data/{signature}/memory/memory.jsonl` — learning
- `data/hidden_agents.json`, `displaying_names.json` — per-tenant UI state (→ DB)

---

## Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Next.js 14+ (App Router)                                        │
│  - Landing, Auth (NextAuth + email + GitHub), Dashboard shell    │
│  - Billing (Stripe), Invites, Leaderboard                         │
└─────────────────────────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
┌──────────────────┐  ┌──────────────────────────────────────────┐
│  PostgreSQL      │  │  Python FastAPI (existing, extended)      │
│  - Users, tenants│  │  - Agent runs, tasks, balance, artifacts  │
│  - Agents,       │  │  - Scoped by user_id / tenant_id          │
│  - Balance/tasks │  │  - Reads/writes DB or files (hybrid)       │
│  - Stripe,       │  └──────────────────────────────────────────┘
│  - Invites       │
└──────────────────┘
```

- **Auth:** NextAuth.js (credentials + GitHub); session has `user.id` (and optional `tenantId` if you add orgs later).
- **Isolation:** Every agent and all economic/task data are keyed by `user_id`. API accepts `X-User-Id` or cookie/session and filters all reads/writes.
- **Storage:** PostgreSQL for users, agents, balance_history, task_completions, token_costs, earnings_log, subscriptions, invites. Optional: keep artifact blobs on S3 or local disk keyed by `user_id/signature/...`.
- **Deploy:** Docker Compose (Next.js, FastAPI, Postgres, Redis optional). One-click templates for Railway / Fly.io / Render.

---

## Implementation Phases

### Phase 1 — Foundation (Auth + DB + Multi-User Isolation)

1. **Next.js 14+ app (App Router)**  
   - New app at `web/`: `app/`, `components/`, `lib/`, `styles/`.  
   - Move or replicate dashboard routes under `app/(dashboard)/`; keep existing Vite app in `frontend/` until migration done, or proxy to it.

2. **Auth (NextAuth.js)**  
   - Providers: Credentials (email + password), GitHub.  
   - DB adapter: store users/sessions in PostgreSQL.  
   - Middleware: protect `/dashboard`, `/api/*` (dashboard API).  
   - Key files: `web/lib/auth.ts`, `web/app/api/auth/[...nextauth]/route.ts`, `web/middleware.ts`.

3. **PostgreSQL + Drizzle**  
   - Schema: `users`, `accounts`, `sessions`, `agents`, `balance_history`, `task_completions`, `token_costs`, `earnings_log`, `display_names`, `hidden_agents` (or `user_settings`).  
   - Location: `packages/db/` with `schema.ts`, `index.ts`, `drizzle.config.ts`.  
   - Migrations: `drizzle-kit generate` + `drizzle-kit migrate`.

4. **Multi-user isolation**  
   - Add `user_id` (and optionally `tenant_id`) to all agent and economic tables.  
   - Python API: accept user context (header or JWT from Next.js). Filter all queries by `user_id`.  
   - Next.js: pass `user.id` to API (server-side fetch or BFF route).

### Phase 2 — Data Migration & API Alignment

5. **Migration script (file → PostgreSQL)**  
   - Read all `agent_data/*/economic/*.jsonl`, `activity_logs`, `work`, `memory`.  
   - Map `signature` → `agent_id` (create agent row with `user_id` from a mapping or default user).  
   - Insert into `balance_history`, `task_completions`, `token_costs`, etc.  
   - Script: `scripts/migrate_file_data_to_postgres.ts` (or `.py` that uses same DB).

6. **FastAPI: optional DB backend**  
   - Either: FastAPI reads from PostgreSQL when `DATABASE_URL` is set (and `user_id` from request).  
   - Or: Next.js BFF reads from DB and proxies to a simplified FastAPI (e.g. only for running agents / streaming).  
   - Prefer: FastAPI remains source of truth for “live” agent runs; it writes to both files (for backward compat) and DB when configured.

### Phase 3 — Deploy & Billing

7. **Docker Compose**  
   - Services: `web` (Next.js), `api` (FastAPI), `postgres`, optional `redis`.  
   - Env: `DATABASE_URL`, `NEXTAUTH_SECRET`, `NEXTAUTH_URL`, `STRIPE_*`, `OPENAI_API_KEY`, etc.  
   - One Dockerfile for Next.js, one for Python API.

8. **Stripe**  
   - Products: e.g. Starter $29/mo, Pro $99/mo; optional “Credits” top-up.  
   - Checkout: Stripe Checkout or Elements; store `subscription_id`, `customer_id` in DB (`subscriptions` table).  
   - Webhooks: `customer.subscription.updated/deleted`, `invoice.paid` → update DB and optionally credits.

9. **README: “Deploy to Railway in 5 minutes”**  
   - Steps: clone, set env vars, deploy with Railway (or Render/Fly) using `docker-compose` or native buildpacks.  
   - Env checklist: `DATABASE_URL`, `NEXTAUTH_SECRET`, `NEXTAUTH_URL`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `OPENAI_API_KEY`.

### Phase 4 — Polish (Landing, Theme, Invites, Leaderboard)

10. **Landing page + dashboard re-theme**  
    - shadcn/ui + Tailwind; high-quality landing (hero, pricing, testimonials, CTA).  
    - Dashboard: same design system; replace current Vite UI gradually or in one pass.

11. **Invite / referral**  
    - Table: `invites` (code, inviter_user_id, invitee_email, used_at, free_months).  
    - Apply free months in Stripe or via a “trial end”/credit in DB.

12. **Analytics + public leaderboard**  
    - Aggregate earnings per user (from `earnings_log` or `task_completions`).  
    - Table: `leaderboard_opt_ins` (user_id, display_name).  
    - Public API/route: top N by earnings (opt-in only).

---

## Key New Files (Scaffold)

| Path | Purpose |
|------|--------|
| `SAAS_PLAN.md` | This plan |
| `packages/db/schema.ts` | Drizzle schema (users, agents, balance, tasks, Stripe, invites) |
| `packages/db/index.ts` | DB client export |
| `packages/db/drizzle.config.ts` | Drizzle config for migrations |
| `web/app/layout.tsx` | Root layout |
| `web/app/(auth)/login/page.tsx` | Login/signup UI |
| `web/app/(dashboard)/layout.tsx` | Dashboard layout (protected) |
| `web/app/(dashboard)/dashboard/page.tsx` | Dashboard home |
| `web/lib/auth.ts` | NextAuth config |
| `web/app/api/auth/[...nextauth]/route.ts` | NextAuth API route |
| `web/middleware.ts` | Auth middleware (protect routes) |
| `scripts/migrate_file_data_to_postgres.ts` | File → Postgres migration |
| `docker-compose.yml` | Web + API + Postgres |
| `web/Dockerfile` | Next.js production image |
| `DEPLOY_RAILWAY.md` or section in README | Deploy guide |

---

## Database Schema (Drizzle) — Summary

- **users** — id, email, name, image, emailVerified, stripeCustomerId, createdAt, updatedAt  
- **accounts** — NextAuth OAuth (userId, provider, providerAccountId, access_token, …)  
- **sessions** — NextAuth (userId, sessionToken, expires)  
- **agents** — id, userId, signature, basemodel, configJson, createdAt (one row per “agent” = signature + user)  
- **balance_history** — id, agentId, date, balance, tokenCostDelta, workIncomeDelta, netWorth, survivalStatus, …  
- **task_completions** — id, agentId, taskId, date, evaluationScore, moneyEarned, wallClockSeconds, …  
- **token_costs** — id, agentId, date, inputTokens, outputTokens, costUsd  
- **earnings_log** — id, userId, agentId, amount, source (work|referral|credit), createdAt (for leaderboard & analytics)  
- **subscriptions** — id, userId, stripeSubscriptionId, stripePriceId, status, currentPeriodEnd, …  
- **invites** — id, code, inviterUserId, inviteeEmail, freeMonths, usedAt, createdAt  
- **user_settings** — userId, hiddenAgentSignatures (json), displayNames (json) — replaces hidden_agents.json / displaying_names.json  

---

## Order of Implementation (Step-by-Step)

1. Add `packages/db` with Drizzle schema and migrations; run against a local Postgres.  
2. Add `web/` Next.js app with App Router; install NextAuth, Drizzle adapter, shadcn/ui.  
3. Implement auth (credentials + GitHub), middleware, and minimal dashboard layout.  
4. Create migration script from current file-based data to PostgreSQL (single default user first).  
5. Extend FastAPI to accept `X-User-Id` (or JWT) and read/write agent and economic data from DB (or via Next.js BFF).  
6. Add Docker Compose (web, api, postgres).  
7. Add Stripe (products, checkout, webhooks, subscriptions table).  
8. Build landing page and re-theme dashboard with shadcn/ui.  
9. Add invite/referral table and logic; optional free months.  
10. Add leaderboard opt-in and public earnings API.  
11. Write “Deploy to Railway in 5 minutes” README section.

---

## Notes

- **Clerk vs NextAuth:** Plan uses NextAuth for full control and self-hosting; Clerk can be swapped in by replacing `lib/auth.ts` and middleware with Clerk’s middleware and components.  
- **Python API:** Prefer keeping FastAPI for agent execution and streaming; add a thin “data” layer that reads/writes Postgres when `user_id` is present.  
- **Artifacts:** Large files (sandbox outputs, terminal logs) can stay on disk or S3 keyed by `user_id/signature/`; metadata in DB.
