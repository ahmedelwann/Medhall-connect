// Admin authentication: single-admin username/password (bcrypt hash stored
// in env, never in the database or repo) + a signed, httpOnly JWT cookie.
//
// This is intentionally simple (one admin account via env vars) rather than
// a full multi-role user-management system, because that is genuinely a
// separate, larger feature. If you need multiple admin accounts with
// different roles, that is listed under "Known Limitations" in
// FINAL_DEPLOYMENT_REPORT.md as NOT IMPLEMENTED.
import jwt from 'jsonwebtoken';
import bcrypt from 'bcryptjs';

const COOKIE_NAME = 'medhall_admin_session';
const SESSION_TTL_SECONDS = 60 * 60 * 8; // 8 hours

function getSecret() {
  const secret = process.env.ADMIN_SESSION_SECRET;
  if (!secret) {
    throw new Error('ADMIN_SESSION_SECRET is not set.');
  }
  return secret;
}

export async function verifyCredentials(username, password) {
  const expectedUser = process.env.ADMIN_USERNAME;
  const expectedHash = process.env.ADMIN_PASSWORD_HASH;
  if (!expectedUser || !expectedHash) {
    throw new Error('ADMIN_USERNAME / ADMIN_PASSWORD_HASH not configured.');
  }
  if (username !== expectedUser) return false;
  return bcrypt.compare(password, expectedHash);
}

export function issueSessionCookie(res) {
  const token = jwt.sign({ role: 'admin' }, getSecret(), { expiresIn: SESSION_TTL_SECONDS });
  res.setHeader(
    'Set-Cookie',
    `${COOKIE_NAME}=${token}; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=${SESSION_TTL_SECONDS}`
  );
}

export function clearSessionCookie(res) {
  res.setHeader('Set-Cookie', `${COOKIE_NAME}=; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=0`);
}

export function getSessionFromRequest(req) {
  const cookieHeader = req.headers.cookie || '';
  const match = cookieHeader.match(new RegExp(`${COOKIE_NAME}=([^;]+)`));
  if (!match) return null;
  try {
    return jwt.verify(match[1], getSecret());
  } catch {
    return null; // expired or tampered — treat as logged out
  }
}

// Wrap an API route so it 401s unless a valid admin session cookie is present.
export function requireAdmin(handler) {
  return async (req, res) => {
    const session = getSessionFromRequest(req);
    if (!session) {
      res.status(401).json({ error: 'Not authenticated' });
      return;
    }
    return handler(req, res, session);
  };
}
