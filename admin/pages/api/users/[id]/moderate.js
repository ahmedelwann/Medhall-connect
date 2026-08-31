import { requireAdmin } from '../../../../lib/auth';
import { query } from '../../../../lib/db';

// action: 'ban' | 'unban' | 'temp_restrict'
// duration_hours: required for temp_restrict, ignored otherwise
export default requireAdmin(async function handler(req, res) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }
  const { id } = req.query;
  const { action, reason, duration_hours } = req.body || {};

  if (!['ban', 'unban', 'temp_restrict'].includes(action)) {
    res.status(400).json({ error: 'Invalid action' });
    return;
  }
  if (action !== 'unban' && !reason) {
    res.status(400).json({ error: 'A reason is required for ban/restrict actions.' });
    return;
  }

  try {
    if (action === 'ban') {
      await query(
        `UPDATE user_profiles SET is_banned = TRUE, ban_reason = $1, ban_until = NULL WHERE internal_user_id = $2`,
        [reason, id]
      );
    } else if (action === 'unban') {
      await query(
        `UPDATE user_profiles SET is_banned = FALSE, ban_reason = NULL, ban_until = NULL WHERE internal_user_id = $1`,
        [id]
      );
    } else if (action === 'temp_restrict') {
      const hours = Number(duration_hours) || 24;
      await query(
        `UPDATE user_profiles SET is_banned = TRUE, ban_reason = $1, ban_until = NOW() + ($2 || ' hours')::interval WHERE internal_user_id = $3`,
        [reason, String(hours), id]
      );
    }

    await query(
      `INSERT INTO audit_log (admin_id, action, resource_type, resource_id, details, created_at)
       VALUES (NULL, $1, 'user', $2, $3, NOW())`,
      [`user_${action}`, id, JSON.stringify({ reason: reason || null, duration_hours: duration_hours || null })]
    );

    res.status(200).json({ ok: true });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: 'Moderation action failed.' });
  }
});
