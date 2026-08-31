import { requireAdmin } from '../../../lib/auth';
import { query } from '../../../lib/db';

// Deliberately returns internal_user_id only — never telegram_id, never
// any field that could deanonymize a participant to the other side of the
// session. Admins reviewing a specific session for a report should use
// the report's evidence + session_messages, not this list.
export default requireAdmin(async function handler(req, res) {
  try {
    const result = await query(
      `SELECT session_id, asker_internal_id, answerer_internal_id, topic,
              status, is_ai_fallback, message_count, created_at, matched_at
       FROM match_sessions
       WHERE status IN ('matching', 'active', 'reported')
       ORDER BY created_at DESC
       LIMIT 100`
    );
    res.status(200).json({ sessions: result.rows });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: 'Failed to load sessions.' });
  }
});
