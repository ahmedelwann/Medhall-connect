# Architecture — MedHall Connect

## Decision: two-host architecture (Option B), not Vercel-only

```
                    GitHub (single repo, two deploy targets)
                    ├── /bot     → Railway or Render (persistent worker)
                    └── /admin   → Vercel (Next.js web app)

Telegram  ⇄  Bot process (long-running, polling)  ⇄  Managed PostgreSQL  ⇄  Admin Panel (Vercel)
                                │
                                └──(after 30s no human)──▶ AI provider (Anthropic API)
```

**Why not run the bot itself on Vercel:** Vercel serverless functions are
request-triggered and time-limited (typically capped at tens of seconds to
a few minutes depending on plan) — they are not designed to hold an
always-on connection to Telegram. The current bot uses
`python-telegram-bot`'s **polling** mode: a single Python process that
stays alive and continuously asks Telegram for updates. That requires a
persistent runtime. Converting it to a webhook would make Vercel
technically possible, but you explicitly asked to keep polling because
it's the architecture that's already implemented and tested in code
review — so the bot goes on a host built for long-running processes
(Railway or Render), and Vercel is used only for what it's actually good
at: a stateless Next.js web app (the admin panel). This is **Option B**
from your original brief, and it is the technically honest choice given
"keep polling."

## Components

| Component | Runs on | Why |
|---|---|---|
| Telegram bot (`bot/medhall_bot.py`) | Railway or Render | Needs a persistent process for polling |
| Admin Panel (`admin/`, Next.js) | Vercel | Stateless request/response web app — exactly what Vercel is for |
| Database | Managed PostgreSQL (Railway Postgres, Render Postgres, Supabase, or Neon) | Both the bot and the admin panel connect to the **same** database over `DATABASE_URL` |
| Redis | Optional, managed (Upstash Redis recommended if used) | See "Is Redis required?" below |
| AI fallback | Anthropic API (or configurable provider) | Called only by the bot process, after the 30s human-match timeout |

## Is Redis required?

**No — it has been made optional, not removed outright.** The original
code didn't actually implement any Redis-backed logic (it imported the
`redis` package but the rate-limiting that shipped was Postgres-based:
`check_rate_limit()` in `medhall_bot.py` queries `session_messages`
directly). Since the actual implementation never depended on Redis, we
kept it optional rather than ripping out the import: if you later add a
distributed job/matching queue across multiple bot instances, Redis is
the natural tool for that, but for a single bot process, Postgres alone
is sufficient and one less moving part to pay for and operate. Leave
`REDIS_URL` blank unless you specifically add Redis-dependent logic.

## Data flow (Ask/Answer)

1. User picks language → discipline → academic level → Ask/Answer → topic → question.
2. Bot creates a `match_sessions` row (`status = matching`).
3. Bot polls the matching engine every 3s for up to `MATCHING_TIMEOUT`
   (default 30s, env-configurable).
4. **Matching engine** (`MatchingEngine.find_best_match`, code-reviewed and
   fixed — see SECURITY.md finding M-01) runs inside a single DB
   transaction using `SELECT ... FOR UPDATE SKIP LOCKED` to pick a
   candidate, then does an atomic `UPDATE match_sessions ... WHERE
   answerer_internal_id IS NULL` to claim it. This means two askers can
   never be matched to the same answerer at the same instant — the second
   transaction's UPDATE simply matches zero rows and falls through.
5. If no human is claimed within the timeout, the bot calls the AI
   fallback chain and tells the user explicitly that AI is answering
   because no human was available (per your requirement — never silently
   pretend AI is human).
6. All messages relay through the bot; neither participant ever receives
   the other's `telegram_id`, username, or any other identifying field —
   only `internal_user_id` (a UUID) is ever exposed, and only to the
   backend/admin, never to the other participant.

## Known architectural limitations (be upfront about these)

- **Single bot process = single point of failure for matching state.**
  The `while elapsed < MATCHING_TIMEOUT` polling loop lives in-process; if
  the bot restarts mid-match, that specific in-flight wait is lost (the
  session row itself survives in Postgres, so it's recoverable, but there
  is no separate durable job queue). For your current scale this is a
  reasonable trade-off; if you need multi-instance/horizontal bot scaling
  later, that in-memory wait loop would need to move to a real queue
  (this is exactly where Redis or Postgres `LISTEN/NOTIFY` would come in).
- **No `admins` table** — the admin panel uses a single admin account via
  environment variables (`ADMIN_USERNAME` / `ADMIN_PASSWORD_HASH`), not a
  multi-user roles system. Multiple admins with different permission
  levels is realistic future work, not something faked here.
- **"Permanent platform ban" is per Telegram account, not per person.**
  Telegram does not expose IP addresses or device identifiers to bots, so
  a ban is enforced by `telegram_id`. A determined user could create a new
  Telegram account. This is a Telegram platform limitation, not a bug —
  documented honestly rather than claiming an unconditional ban.
