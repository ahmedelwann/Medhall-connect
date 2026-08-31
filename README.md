# MedHall Connect

Anonymous, discipline-matched Q&A for medical-field students, over
Telegram, with an AI fallback when no human answerer is available in
time — and a separate Admin Panel for moderation.

Official channel: https://t.me/medhalll

## Repo layout

```
MedHall-Connect/
├── bot/                    Telegram bot (Python, polling) — deploy to Railway/Render
│   ├── medhall_bot.py
│   ├── requirements.txt
│   └── tests/test_medhall.py
├── admin/                  Admin Panel (Next.js) — deploy to Vercel
│   ├── pages/
│   ├── lib/
│   └── scripts/hash-password.js
├── database/
│   └── database_schema.sql
├── .env.example
├── ARCHITECTURE.md         Why two hosts, not Vercel-only, and how matching works
├── DEPLOYMENT.md           Exact step-by-step deploy instructions
├── OWNER_GUIDE.md          Day-to-day operation, no coding required
├── SECURITY.md             Manual code-review findings and fixes
├── TEST_REPORT.md          What was and was NOT verified, and why
├── FINAL_DEPLOYMENT_REPORT.md
├── PRIVACY_POLICY.md
├── TERMS_OF_SERVICE.md
└── MEDICAL_DISCLAIMER.md
```

## Start here

1. **First-time setup:** DEPLOYMENT.md (database → bot host → admin panel → Telegram token)
2. **Running it day-to-day:** OWNER_GUIDE.md
3. **Why it's built this way:** ARCHITECTURE.md
4. **What was actually verified vs. not:** TEST_REPORT.md and FINAL_DEPLOYMENT_REPORT.md — read these before assuming anything is production-ready

## Important, upfront

This repository was prepared in an offline environment (no internet
access, no live database, no Telegram API access). The code was
rewritten and manually reviewed to fix real bugs found during review
(see SECURITY.md), but **none of it has been executed** — not the
Python tests, not the database schema against a live Postgres, not the
admin panel's `npm run build`, not a real Telegram conversation. Read
TEST_REPORT.md and run those steps yourself before trusting this with
real users. This is stated plainly rather than claiming
"PRODUCTION READY" without evidence.

## Zero local infrastructure required to *run* this in production
You do not need Docker, a local PostgreSQL, local Redis, or a local
Python install to deploy or operate this day-to-day — everything runs on
managed cloud services (Railway/Render + Vercel + managed Postgres). A
local Python/Node setup is only needed if you want to run the test suite
or develop locally, which is optional.
