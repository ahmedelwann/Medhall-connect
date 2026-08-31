import { requireAdmin } from '../../../lib/auth';
import { query } from '../../../lib/db';

export default requireAdmin(async function handler(req, res) {
  try {
    const result = await query(
      `SELECT id, admin_id, action, resource_type, resource_id, details, ip_address, created_at
       FROM audit_log
       ORDER BY created_at DESC
       LIMIT 200`
    );
    res.status(200).json({ entries: result.rows });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: 'Failed to load audit log.' });
  }
});
