import { verifyCredentials, issueSessionCookie } from '../../../lib/auth';
import { query } from '../../../lib/db';

// Very small in-memory rate limiter per serverless instance. This is a
// best-effort mitigation, not a hard guarantee, because Vercel serverless
// functions do not share memory across invocations/regions. For a hard
// guarantee, back this with Redis or the shared Postgres rate_limit table.
const attempts = new Map();
const MAX_ATTEMPTS = 5;
const WINDOW_MS = 5 * 60 * 1000;

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }

  const ip = req.headers['x-forwarded-for'] || req.socket?.remoteAddress || 'unknown';
  const now = Date.now();
  const record = attempts.get(ip) || { count: 0, windowStart: now };
  if (now - record.windowStart > WINDOW_MS) {
    record.count = 0;
    record.windowStart = now;
  }
  if (record.count >= MAX_ATTEMPTS) {
    res.status(429).json({ error: 'Too many login attempts. Try again later.' });
    return;
  }

  const { username, password } = req.body || {};
  if (!username || !password) {
    res.status(400).json({ error: 'Username and password are required.' });
    return;
  }

  let ok = false;
  try {
    ok = await verifyCredentials(username, password);
  } catch (e) {
    res.status(500).json({ error: 'Admin auth is not configured on the server.' });
    return;
  }

  record.count += 1;
  attempts.set(ip, record);

  if (!ok) {
    res.status(401).json({ error: 'Invalid credentials' });
    return;
  }

  issueSessionCookie(res);

  // Audit log — login success. Failure attempts are intentionally not
  // written to the audit table (would let an attacker fill it / doesn't
  // add much over server logs), but ARE rate-limited above.
  try {
    // NOTE: the schema has no `admins` table (single env-var admin only —
    // see Known Limitations), so admin_id stays NULL and the username is
    // recorded in `details` instead.
    await query(
      `INSERT INTO audit_log (admin_id, action, details, ip_address, created_at) VALUES (NULL, $1, $2, $3, NOW())`,
      ['admin_login', JSON.stringify({ username }), String(ip).split(',')[0].trim()]
    );
  } catch (e) {
    // Do not fail the login just because audit logging failed; log server-side instead.
    console.error('audit_log insert failed (login still succeeds):', e.message);
  }

  res.status(200).json({ ok: true });
}
