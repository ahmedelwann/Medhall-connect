import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import Layout from '../components/Layout';

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState('');
  const router = useRouter();

  useEffect(() => {
    fetch('/api/dashboard').then(async (res) => {
      if (res.status === 401) {
        router.push('/login');
        return;
      }
      const data = await res.json();
      if (!res.ok) {
        setError(data.error);
        return;
      }
      setStats(data);
    });
  }, []);

  const cards = stats
    ? [
        ['Total users', stats.total_users],
        ['Active sessions', stats.active_sessions],
        ['Pending reports', stats.pending_reports],
        ['AI calls (24h)', stats.ai_calls_today],
        ['Banned users', stats.banned_users],
      ]
    : [];

  return (
    <Layout>
      <h1>Dashboard</h1>
      {error && <p style={{ color: '#dc2626' }}>{error}</p>}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16, marginTop: 16 }}>
        {cards.map(([label, value]) => (
          <div key={label} style={{ background: '#fff', borderRadius: 10, padding: 20, boxShadow: '0 1px 2px rgba(0,0,0,0.06)' }}>
            <div style={{ fontSize: 13, color: '#64748b' }}>{label}</div>
            <div style={{ fontSize: 28, fontWeight: 700 }}>{value ?? '—'}</div>
          </div>
        ))}
      </div>
      <p style={{ marginTop: 24, fontSize: 13, color: '#64748b' }}>
        Bot status is not shown here directly — check the bot host's own dashboard
        (Railway/Render) for process uptime, or query the bot's health endpoint if you add one.
      </p>
    </Layout>
  );
}
