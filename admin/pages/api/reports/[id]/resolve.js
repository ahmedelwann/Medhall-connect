import { requireAdmin } from '../../../../lib/auth';
import { query } from '../../../../lib/db';

export default requireAdmin(async function handler(req, res) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }
  const { id } = req.query;
  const { notes } = req.body || {};

  try {
    await query(`UPDATE reports SET status = 'resolved' WHERE report_id = $1`, [id]);
    await query(
      `INSERT INTO audit_log (admin_id, action, resource_type, resource_id, details, created_at)
       VALUES (NULL, 'report_resolved', 'report', $1, $2, NOW())`,
      [id, JSON.stringify({ notes: notes || null })]
    );
    res.status(200).json({ ok: true });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: 'Failed to resolve report.' });
  }
});
