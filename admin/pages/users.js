import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import Layout from '../components/Layout';

export default function Users() {
  const [q, setQ] = useState('');
  const [users, setUsers] = useState([]);
  const [busyId, setBusyId] = useState(null);
  const router = useRouter();

  async function load() {
    const res = await fetch(`/api/users?q=${encodeURIComponent(q)}`);
    if (res.status === 401) return router.push('/login');
    const data = await res.json();
    setUsers(data.users || []);
  }

  useEffect(() => { load(); }, []);

  async function moderate(id, action) {
    let reason = null;
    if (action !== 'unban') {
      reason = prompt(`Reason for ${action} (required, shown in audit log):`);
      if (!reason) return;
    }
    setBusyId(id);
    try {
      const res = await fetch(`/api/users/${id}/moderate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, reason }),
      });
      if (!res.ok) {
        const data = await res.json();
        alert(data.error || 'Action failed');
      }
      await load();
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Layout>
      <h1>Users</h1>
      <p style={{ fontSize: 13, color: '#64748b' }}>
        Search is by internal user ID only (from a report or session record) —
        the panel never links a user's real Telegram identity.
      </p>
      <div style={{ display: 'flex', gap: 8, margin: '12px 0' }}>
        <input
          placeholder="internal_user_id (or leave blank for most recent)"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ flex: 1, padding: 8, borderRadius: 6, border: '1px solid #cbd5e1' }}
        />
        <button onClick={load} style={{ padding: '8px 16px', borderRadius: 6, border: 'none', background: '#2563eb', color: '#fff' }}>
          Search
        </button>
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', background: '#fff' }}>
        <thead>
          <tr style={{ textAlign: 'left', borderBottom: '1px solid #e2e8f0' }}>
            <th style={th}>Internal ID</th>
            <th style={th}>Field</th>
            <th style={th}>Level</th>
            <th style={th}>Status</th>
            <th style={th}>Reputation</th>
            <th style={th}>Risk</th>
            <th style={th}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.internal_user_id} style={{ borderBottom: '1px solid #f1f5f9' }}>
              <td style={td}><code>{u.internal_user_id.slice(0, 8)}…</code></td>
              <td style={td}>{u.field}</td>
              <td style={td}>{u.academic_level}</td>
              <td style={td}>{u.is_banned ? `Banned${u.ban_until ? ' (temp)' : ''}` : 'Active'}</td>
              <td style={td}>{u.reputation_score}</td>
              <td style={td}>{u.risk_score}</td>
              <td style={td}>
                {u.is_banned ? (
                  <button disabled={busyId === u.internal_user_id} onClick={() => moderate(u.internal_user_id, 'unban')}>Unban</button>
                ) : (
                  <>
                    <button disabled={busyId === u.internal_user_id} onClick={() => moderate(u.internal_user_id, 'temp_restrict')} style={{ marginRight: 6 }}>
                      Temp restrict
                    </button>
                    <button disabled={busyId === u.internal_user_id} onClick={() => moderate(u.internal_user_id, 'ban')}>Ban</button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Layout>
  );
}

const th = { padding: '10px 8px', fontSize: 12, color: '#64748b', textTransform: 'uppercase' };
const td = { padding: '10px 8px', fontSize: 14 };
