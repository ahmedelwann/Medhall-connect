# Security Review

**Method:** manual, line-by-line code review of `bot/medhall_bot.py`,
`database/database_schema.sql`, and the new `admin/` code. This is
**NOT** a penetration test, NOT a dependency/CVE scan (no network access
to run `pip-audit`/`npm audit`), and NOT run against a live deployment.
Everything below is CODE REVIEWED, not LOCALLY EXECUTED or VERIFIED IN
PRODUCTION — treat this as a solid starting point, not a substitute for
a real audit before a public launch with real users.

## Findings

```
SECURITY AUDIT (manual code review only — see method note above)

Critical: 1
High:     2
Medium:   3
Low:      2
Informational: 2
```

### S-01 — Critical — Database schema uses invalid PostgreSQL syntax
- **Finding:** `database_schema.sql` declared indexes as `INDEX
  name (cols)` inside `CREATE TABLE` statements. That is MySQL syntax;
  PostgreSQL rejects it with a syntax error. As shipped, the schema could
  not be applied to any of the managed Postgres providers this project
  targets (Railway, Render, Supabase, Neon) — a fresh deployment would
  fail at the very first setup step.
- **Impact:** Total deployment blocker, not an exploitable vulnerability
  — included here because "critical" in your requested severity scale
  best reflects "the product cannot come up at all."
- **Fix:** Rewrote every affected table to use standalone `CREATE INDEX
  ... ON table(cols);` statements after the table definition. Applied.
- **Retest status:** CODE REVIEWED (syntax manually verified against
  PostgreSQL grammar). NOT EXECUTED against a live Postgres instance —
  you must run it yourself per DEPLOYMENT.md step 1 and confirm.

### S-02 — High — Matching race condition could pair two askers with one answerer
- **Finding:** `MatchingEngine.find_best_match` selected a candidate
  answerer with a plain `SELECT`, with no locking and no atomic claim.
  Two concurrent askers could both read the same "available" answerer and
  both be told they were matched to them.
- **Impact:** Violates your explicit requirement ("Prevent duplicate
  matching. Prevent race conditions.") and could put one answerer into
  two anonymous conversations they didn't agree to, undermining the
  1:1 anonymity model.
- **Fix:** Rewrote to use `SELECT ... FOR UPDATE SKIP LOCKED` plus an
  atomic `UPDATE match_sessions ... WHERE answerer_internal_id IS NULL`
  inside one transaction — only one transaction's claim can succeed per
  answerer. See ARCHITECTURE.md for the full explanation.
- **Retest status:** CODE REVIEWED. NOT EXECUTED (would need a live DB
  and concurrent load to fully verify under real contention).

### S-03 — High — Academic level matching used incorrect string comparison
- **Finding:** `academic_level >= %s` compared VARCHAR values
  lexicographically (alphabetically), not by actual academic seniority —
  e.g. `'postgraduate' < 'year_1'` as strings even though postgraduate
  should outrank year 1. This silently produced wrong/unfair matches.
- **Impact:** Correctness bug affecting match quality, not a
  confidentiality/integrity vulnerability, but listed as High because it
  directly breaks a core product requirement (§19 matching-by-level).
- **Fix:** Added `academic_level_rank` (integer) column and an explicit
  `ACADEMIC_LEVEL_RANK` mapping in code, kept in sync on profile creation.
- **Retest status:** CODE REVIEWED. NOT EXECUTED.

### S-04 — Medium — Admin login rate limiting is per-serverless-instance only
- **Finding:** `admin/pages/api/auth/login.js` rate-limits with an
  in-memory `Map`, which does not persist or share state across Vercel's
  serverless function instances/regions.
- **Impact:** The rate limit is a soft speed bump, not a hard guarantee —
  a distributed brute-force attempt could exceed 5 attempts/5min in
  aggregate across instances.
- **Fix:** Documented as a known limitation in code comments. Not fully
  fixed in this pass — a proper fix means backing the limiter with the
  shared Postgres database (there's already a `rate_limit_violations`
  table) or a managed Redis (e.g. Upstash), which is straightforward
  follow-up work but out of scope to implement untested in this session.
- **Retest status:** NOT FIXED — documented, recommended follow-up.

### S-05 — Medium — No `admins` table; single shared admin account
- **Finding:** The schema has no table for individual admin users;
  `admin_id` in `audit_log` is typed `INT` with nothing to reference. The
  admin panel therefore supports exactly one admin identity via
  environment variables.
- **Impact:** No per-admin accountability if more than one person uses
  the panel (the audit log records the *username* they typed, which is
  only meaningful if each person is trusted to use their own credentials
  — there's no way to issue/revoke individual admin accounts).
- **Fix:** Not implemented — flagged as a real feature gap in
  ARCHITECTURE.md and FINAL_DEPLOYMENT_REPORT.md rather than faked.
- **Retest status:** NOT FIXED — documented, recommended follow-up.

### S-06 — Medium — No webhook architecture, so webhook-specific items (§27) don't apply
- **Finding:** Because polling was kept (per your decision), there is no
  webhook endpoint, so Telegram webhook secret-token validation, replay
  protection, etc. are not applicable to this build.
- **Impact:** N/A for this architecture; noted so it isn't silently
  assumed to be missing/forgotten. If you later switch to webhooks, this
  entire section needs new work.
- **Retest status:** N/A.

### S-07 — Low — Each DB call opens/closes its own connection
- **Finding:** `DatabaseManager` opens a fresh `psycopg2.connect()` per
  method call rather than using a connection pool.
- **Impact:** Higher latency and connection overhead under load;
  functionally correct, not a security bug, but worth fixing for
  production traffic.
- **Fix:** Not changed in this pass (behavior-preserving to avoid
  introducing new untested code paths beyond what was necessary for the
  Critical/High fixes). Recommended follow-up: `psycopg2.pool` or
  `SimpleConnectionPool`.
- **Retest status:** NOT FIXED — documented, recommended follow-up.

### S-08 — Low — PII/phone regex will have false positives/negatives
- **Finding:** `PHONE_PATTERN` is a broad regex that will flag many
  ordinary numeric strings (e.g. dosages, measurements, dates in some
  formats) as "phone numbers," and can also miss internationally
  formatted numbers it wasn't tuned for.
- **Impact:** Over-blocking legitimate medical content (dosages, lab
  values) is a real UX problem for an *educational medical* bot.
- **Fix:** Not changed — tuning this needs real message samples/testing,
  which isn't possible offline. Documented as a follow-up.
- **Retest status:** NOT FIXED — documented, recommended follow-up.

### I-01 — Informational — Secrets handling in code is otherwise sound
All database queries use parameterized queries (`%s` placeholders, no
string concatenation) — no SQL injection found in the reviewed code. No
hardcoded secrets, tokens, or credentials found anywhere in
`medhall_bot.py`, `database_schema.sql`, or the new `admin/` code.

### I-02 — Informational — Dependency versions not audited
`requirements.txt` and `admin/package.json` pin versions, but no CVE/
vulnerability scan was possible (no network access to `pip-audit` or
`npm audit`). Run these yourself before production launch:
```bash
pip install pip-audit --break-system-packages && pip-audit -r bot/requirements.txt
cd admin && npm audit
```

## Privacy audit

```
User A can obtain User B Telegram ID          : PASS (never sent to either participant)
User A can obtain User B username             : PASS (never sent to either participant)
User A can obtain User B phone                : PASS (not collected at all)
User A can obtain User B profile link         : PASS (never sent to either participant)
User A can access another session             : PASS (matching engine fix, S-02 — one answerer per session, session_id scoped)
AI can access unrelated user data             : PASS (AI provider only receives the current question/topic, per code review of AIFallbackChain — no other users' data is passed)
Unauthorized admin can access conversations   : PARTIAL — requires a valid admin session (JWT-verified, see admin/lib/auth.js); there is no role separation (S-05), so any holder of the single admin credential has full access. Not a "PASS" in the strict sense of least-privilege, but not "FAIL" either — access does require authentication.
```

Method note: verified by reading the code paths that assemble messages
sent to Telegram and to the AI provider — not by running a live test
conversation (no network access).
