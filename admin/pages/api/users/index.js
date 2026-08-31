import { requireAdmin } from '../../../lib/auth';
import { query } from '../../../lib/db';

// Search users by internal_user_id (never by telegram_id/name over this
// API — admins can look up the internal ID from a report, but the panel
// intentionally does not expose a "search by real Telegram username"
// shortcut, to keep the same identity-minimization discipline the bot
// itself enforces between participants).
export default requireAdmin(async function handler(req, res) {
  const search = (req.query.q || '').trim();
  try {
    const result = await query(
      `SELECT internal_user_id, field, academic_level, country, is_banned,
              ban_reason, ban_until, reputation_score, risk_score, created_at, last_active
       FROM user_profiles
       WHERE ($1 = '' OR internal_user_id::text ILIKE '%' || $1 || '%')
       ORDER BY last_active DESC
       LIMIT 50`,
      [search]
    );
    res.status(200).json({ users: result.rows });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: 'Failed to search users.' });
  }
});
