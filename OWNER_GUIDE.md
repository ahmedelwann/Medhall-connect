# Owner Guide (No Coding Knowledge Required)

This explains day-to-day operation. For the one-time setup, see
DEPLOYMENT.md first — do that once, then use this guide going forward.

## 1. How to deploy (first time)
Follow DEPLOYMENT.md steps 1–4, in order: database → bot host
(Railway/Render) → admin panel (Vercel) → Telegram token. After that,
"deploying" just means pushing code to GitHub (see §9).

## 2. Where to put the Telegram token
Railway (or Render) → your bot service → **Variables/Environment** tab →
`TELEGRAM_BOT_TOKEN`. Never put it in a file in the repo.

## 3. Where to put AI credentials
Same place as the token (Railway/Render → Variables) → `AI_API_KEY`,
`AI_PROVIDER`, `AI_MODEL`.

## 4. Where the Admin Panel is
`https://YOUR-PROJECT-NAME.vercel.app/login` — the exact address is
shown on your Vercel project's dashboard page after you deploy it (under
the project name, labeled "Domains").

## 5. How to ban a user
Admin Panel → **Users** → search by the internal user ID (you'll usually
get this from a report) → click **Ban** → type a reason → confirm. To
lift it later, click **Unban** on the same row. Use **Temp restrict**
instead of Ban for a time-limited restriction.

## 6. How to review reports
Admin Panel → **Reports** → the "Pending" tab shows open reports with the
reason and any evidence text → after you've handled one, click **Mark
resolved** and optionally leave a note. The "Resolved" tab keeps history.

## 7. How to review conversations under the privacy policy
This build does **not** yet include a conversation-transcript viewer in
the admin UI — flagged/reported messages are stored in the
`session_messages` table with `is_flagged` set, but there is no page to
browse them yet. For now, reviewing a specific reported conversation
requires a direct database query (e.g. via your Postgres provider's SQL
console):
```sql
SELECT sender_internal_id, content, is_flagged, flag_reason, created_at
FROM session_messages
WHERE session_id = 'THE_SESSION_ID_FROM_THE_REPORT'
ORDER BY created_at;
```
Anyone doing this should already have been told, per the Privacy Policy,
that conversations may be reviewed for abuse investigation/reports/
security — this capability exists, it's just not yet wrapped in a UI
button. That's listed as a known gap, not hidden.

## 8. How to stop/restart the bot
- **Railway**: your service → **⋮** menu → Restart (or Remove to stop
  entirely). Crashes auto-restart on their own; this is for manual
  intervention.
- **Render**: your service → **Manual Deploy → Restart service**, or
  **Suspend** to stop billing/traffic entirely.

## 9. How to update the bot from GitHub
Edit code (yourself, or ask an assistant to), then:
```bash
git add .
git commit -m "describe the change"
git push
```
Both Railway/Render and Vercel are already watching your GitHub repo —
pushing triggers a new deploy on each automatically. No manual redeploy
click needed (though you can also click "Redeploy" in either dashboard
if you just want to restart with the same code).

## 10. How to change configuration
Most settings are environment variables, not code:
`MATCHING_TIMEOUT`, `MAX_DAILY_AI_USAGE`, `MESSAGE_RATE_LIMIT`, `AI_MODEL`.
Change them in Railway/Render → Variables → the service restarts itself
automatically when you save a variable change. No GitHub push needed for
these.

## 11. How to check if the bot is online
- Quickest: open Telegram, message your bot `/start`, see if it replies.
- Railway/Render dashboard → your service → **Logs** tab → recent log
  lines with timestamps close to "now" mean it's running.
- There is currently no separate `/health` HTTP endpoint on the bot
  itself (it's a polling process, not a web server) — this is a
  reasonable future addition, not something implemented here.

## 12. How to roll back a bad deployment
See DEPLOYMENT.md → "Rollback" section — it's a few clicks in each
platform's dashboard (Vercel: "Promote to Production" on an older
deployment; Railway/Render: "Redeploy"/"Rollback" on an older deployment)
and does not require touching git or code.
