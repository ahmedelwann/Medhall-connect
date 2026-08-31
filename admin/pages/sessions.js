import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import Layout from '../components/Layout';

export default function Sessions() {
  const [sessions, setSessions] = useState([]);
  const router = useRouter();

  useEffect(() => {
    fetch('/api/sessions').then(async (res) => {
      if (res.status === 401) return router.push('/login');
      const data = await res.json();
      setSessions(data.sessions || []);
    });
  }, []);

  return (
    <Layout>
      <h1>Sessions</h1>
      <table style={{ width: '100%', borderCollapse: 'collapse', background: '#fff' }}>
        <thead>
          <tr style={{ textAlign: 'left', borderBottom: '1px solid #e2e8f0' }}>
            <th style={th}>Session</th>
            <th style={th}>Topic</th>
            <th style={th}>Status</th>
            <th style={th}>AI fallback?</th>
            <th style={th}>Messages</th>
            <th style={th}>Started</th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((s) => (
            <tr key={s.session_id} style={{ borderBottom: '1px solid #f1f5f9' }}>
              <td style={td}><code>{s.session_id.slice(0, 8)}…</code></td>
              <td style={td}>{s.topic}</td>
              <td style={td}>{s.status}</td>
              <td style={td}>{s.is_ai_fallback ? 'Yes' : 'No'}</td>
              <td style={td}>{s.message_count}</td>
              <td style={td}>{new Date(s.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {sessions.length === 0 && <p style={{ color: '#64748b' }}>No active/matching/reported sessions.</p>}
    </Layout>
  );
}

const th = { padding: '10px 8px', fontSize: 12, color: '#64748b', textTransform: 'uppercase' };
const td = { padding: '10px 8px', fontSize: 14 };
