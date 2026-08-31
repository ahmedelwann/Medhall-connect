import { requireAdmin } from '../../lib/auth';
import { query } from '../../lib/db';

// NOT EXECUTED against a live database — reviewed by hand, not runtime-verified.
export default requireAdmin(async function handler(req, res) {
  try {
    const [users, activeSessions, pendingReports, aiUsageToday, bannedUsers] = await Promise.all([
      query(`SELECT COUNT(*)::int AS count FROM user_profiles`),
      query(`SELECT COUNT(*)::int AS count FROM match_sessions WHERE status = 'active'`),
      query(`SELECT COUNT(*)::int AS count FROM reports WHERE status = 'open'`),
      query(`SELECT COUNT(*)::int AS count FROM ai_usage WHERE created_at > NOW() - INTERVAL '1 day'`),
      query(`SELECT COUNT(*)::int AS count FROM user_profiles WHERE is_banned = TRUE`),
    ]);

    res.status(200).json({
      total_users: users.rows[0].count,
      active_sessions: activeSessions.rows[0].count,
      pending_reports: pendingReports.rows[0].count,
      ai_calls_today: aiUsageToday.rows[0].count,
      banned_users: bannedUsers.rows[0].count,
    });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: 'Failed to load dashboard stats. Check DATABASE_URL and that the schema has been applied.' });
  }
});
