import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import Layout from '../components/Layout';

export default function Reports() {
  const [status, setStatus] = useState('open');
  const [reports, setReports] = useState([]);
  const router = useRouter();

  async function load(s) {
    const res = await fetch(`/api/reports?status=${s}`);
    if (res.status === 401) return router.push('/login');
    const data = await res.json();
    setReports(data.reports || []);
  }

  useEffect(() => { load(status); }, [status]);

  async function resolve(id) {
    const notes = prompt('Internal resolution notes (optional):') || '';
    const res = await fetch(`/api/reports/${id}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes }),
    });
    if (res.ok) load(status);
  }

  return (
    <Layout>
      <h1>Reports</h1>
      <div style={{ marginBottom: 12 }}>
        <button onClick={() => setStatus('open')} style={{ fontWeight: status === 'open' ? 700 : 400, marginRight: 12 }}>Pending</button>
        <button onClick={() => setStatus('resolved')} style={{ fontWeight: status === 'resolved' ? 700 : 400 }}>Resolved</button>
      </div>
      {reports.map((r) => (
        <div key={r.report_id} style={{ background: '#fff', borderRadius: 8, padding: 16, marginBottom: 10 }}>
          <div style={{ fontSize: 12, color: '#64748b' }}>{new Date(r.created_at).toLocaleString()} — session {r.session_id.slice(0, 8)}…</div>
          <div style={{ margin: '6px 0' }}><strong>Reason:</strong> {r.reason}</div>
          {r.evidence && <div style={{ fontSize: 13, color: '#334155' }}><strong>Evidence:</strong> {r.evidence}</div>}
          <div style={{ fontSize: 12, color: '#64748b', marginTop: 6 }}>
            Reporter {r.reporter_internal_id.slice(0, 8)}… → Reported {r.reported_internal_id.slice(0, 8)}…
          </div>
          {status === 'open' && (
            <button onClick={() => resolve(r.report_id)} style={{ marginTop: 10, padding: '6px 12px', borderRadius: 6, border: 'none', background: '#16a34a', color: '#fff' }}>
              Mark resolved
            </button>
          )}
        </div>
      ))}
      {reports.length === 0 && <p style={{ color: '#64748b' }}>No {status} reports.</p>}
    </Layout>
  );
}
