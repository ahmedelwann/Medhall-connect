// Shared Postgres connection pool for all admin API routes.
// Uses the SAME DATABASE_URL as the bot (see /.env.example) so the admin
// panel reads/writes the exact data the bot produces — no data duplication.
//
// NOT EXECUTED: no live Postgres instance / network access was available
// in the environment that produced this code, so this has been reviewed
// by hand for correctness but not run against a real database.
import { Pool } from 'pg';

let pool;

export function getPool() {
  if (!pool) {
    if (!process.env.DATABASE_URL) {
      throw new Error('DATABASE_URL is not set. Add it in Vercel → Project → Settings → Environment Variables.');
    }
    pool = new Pool({
      connectionString: process.env.DATABASE_URL,
      ssl: { rejectUnauthorized: false }, // required by most managed Postgres providers
      max: 5, // Vercel serverless functions are short-lived; keep the pool small
    });
  }
  return pool;
}

export async function query(text, params) {
  const client = getPool();
  return client.query(text, params);
}
