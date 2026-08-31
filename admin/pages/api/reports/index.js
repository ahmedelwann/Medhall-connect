import { requireAdmin } from '../../../lib/auth';
import { query } from '../../../lib/db';

export default requireAdmin(async function handler(req, res) {
  const status = req.query.status === 'resolved' ? 'resolved' : 'open';
  try {
    const result = await query(
      `SELECT report_id, session_id, reporter_internal_id, reported_internal_id,
              reason, evidence, status, created_at
       FROM reports
       WHERE status = $1
       ORDER BY created_at DESC
       LIMIT 100`,
      [status]
    );
    res.status(200).json({ reports: result.rows });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: 'Failed to load reports.' });
  }
});
