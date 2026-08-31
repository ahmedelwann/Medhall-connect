# Deployment Guide

Two independent deploys from **one GitHub repo**: the bot (Railway or
Render) and the admin panel (Vercel). Do both once; after that, every
`git push` to `main` redeploys both automatically.

## 0. Push this repo to GitHub

```bash
git init
git add .
git commit -m "MedHall Connect - initial GitHub-ready import"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/MedHall-Connect.git
git push -u origin main
```

## 1. Create the managed database first

Pick **one**: Railway Postgres, Render Postgres, Supabase, or Neon. Any
standard managed Postgres 12+ works — the schema has no provider-specific
extensions.

1. Create a new Postgres instance on your chosen provider.
2. Copy its connection string — you'll set this as `DATABASE_URL` on
   **both** the bot host and Vercel.
3. Apply the schema **once**:
   ```bash
   psql "$DATABASE_URL" -f database/database_schema.sql
   ```
   (Most providers also let you paste this into a web-based SQL console —
   Supabase's SQL Editor and Neon's SQL Editor both work directly.)

   This step could not be run in the environment that produced this
   repo (no network/database access) — the file was reviewed by hand and
   a MySQL-syntax bug was found and fixed (see SECURITY.md, finding
   S-01), but **you must run it yourself and confirm it completes without
   errors** before going further.

## 2. Deploy the bot — Railway (recommended) or Render

**Why Railway is the better default here:** both support persistent
Python worker processes with auto-restart, but Railway's free/starter
tier billing is usage-based per-second and its dashboard makes
"deploy from GitHub repo subfolder" (`/bot`) slightly more
straightforward out of the box. Render is an equally valid choice — pick
it instead if you prefer Render's simpler flat monthly pricing (its free
tier for background workers is more limited and can spin down, which is
undesirable for a bot that must poll continuously — use at least Render's
paid "Background Worker" tier if you go this route, not the free web
service tier).

### Railway steps
1. [railway.app](https://railway.app) → New Project → Deploy from GitHub repo → select this repo.
2. Set **Root Directory** to `bot`.
3. Railway auto-detects Python; confirm the start command is:
   ```
   python medhall_bot.py
   ```
4. Add environment variables (Project → Variables): `TELEGRAM_BOT_TOKEN`,
   `DATABASE_URL`, `AI_PROVIDER`, `AI_MODEL`, `AI_API_KEY`,
   `ENCRYPTION_KEY`, `MATCHING_TIMEOUT`, `MAX_DAILY_AI_USAGE`,
   `MESSAGE_RATE_LIMIT`, and `REDIS_URL` only if you're using Redis.
5. Deploy. Railway restarts the process automatically on crash by default
   (this is a platform feature, not something this repo configures).

### Render steps (alternative)
1. [render.com](https://render.com) → New → Background Worker → connect this GitHub repo.
2. Root Directory: `bot`. Build command: `pip install -r requirements.txt`. Start command: `python medhall_bot.py`.
3. Add the same environment variables as above under Environment.
4. Choose a paid instance type (not the free web tier) so the worker
   doesn't spin down.

## 3. Deploy the admin panel — Vercel

1. [vercel.com](https://vercel.com) → Add New → Project → import this
   GitHub repo.
2. Set **Root Directory** to `admin` (Vercel's project settings, not a
   custom `vercel.json` — this is the standard, least error-prone way to
   deploy a subfolder of a monorepo).
3. Framework preset: Next.js (auto-detected).
4. Before deploying, generate your admin password hash locally:
   ```bash
   cd admin
   npm install
   node scripts/hash-password.js "your-strong-password"
   ```
5. Add environment variables in Vercel → Project → Settings →
   Environment Variables: `DATABASE_URL` (same value as the bot host),
   `ADMIN_SESSION_SECRET` (generate with `openssl rand -base64 32`),
   `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH` (from step 4).
6. Deploy. Your admin panel is now at:
   ```
   https://YOUR-PROJECT-NAME.vercel.app/login
   ```
   (Vercel assigns the exact subdomain when you create the project —
   this repo does not invent or hard-code a domain.)

## 4. Point the Telegram bot at your token

In [@BotFather](https://t.me/BotFather) on Telegram: `/newbot` (or
`/token` for an existing bot) → copy the token → paste it as
`TELEGRAM_BOT_TOKEN` in Railway/Render (step 2.4/2.5 above), **never** in
the repo. Restart the bot service if it was already running.

## 5. Confirm it's live

- Open your bot in Telegram and send `/start`.
- Open `https://YOUR-PROJECT-NAME.vercel.app/login`, sign in, and the
  Dashboard should show `total_users` incrementing as people start the
  bot.

## Automatic redeploys

Both Railway/Render and Vercel watch the GitHub repo by default: a
`git push` to `main` triggers a new build and deploy on both platforms
automatically. Nothing extra to configure.

## Rollback

- **Vercel**: Project → Deployments → find the last known-good
  deployment → "Promote to Production" (three-dot menu). Instant, no
  rebuild needed.
- **Railway**: Project → Deployments tab → select a previous successful
  deployment → "Redeploy".
- **Render**: Service → Events/Deploys tab → select a previous deploy →
  "Rollback to this deploy".

In all three cases this reverts the *running* deployment, not your git
history — your `main` branch is unaffected, so you can fix forward with a
new commit afterward.
