import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import Layout from '../components/Layout';

export default function Audit() {
  const [entries, setEntries] = useState([]);
  const router = useRouter();

  useEffect(() => {
    fetch('/api/audit').then(async (res) => {
      if (res.status === 401) return router.push('/login');
      const data = await res.json();
      setEntries(data.entries || []);
    });
  }, []);

  return (
    <Layout>
      <h1>Audit Log</h1>
      <table style={{ width: '100%', borderCollapse: 'collapse', background: '#fff' }}>
        <thead>
          <tr style={{ textAlign: 'left', borderBottom: '1px solid #e2e8f0' }}>
            <th style={th}>When</th>
            <th style={th}>Action</th>
            <th style={th}>Resource</th>
            <th style={th}>Details</th>
            <th style={th}>IP</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
              <td style={td}>{new Date(e.created_at).toLocaleString()}</td>
              <td style={td}>{e.action}</td>
              <td style={td}>{e.resource_type ? `${e.resource_type}:${String(e.resource_id).slice(0, 8)}` : '—'}</td>
              <td style={td}><code style={{ fontSize: 12 }}>{JSON.stringify(e.details)}</code></td>
              <td style={td}>{e.ip_address || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Layout>
  );
}

const th = { padding: '10px 8px', fontSize: 12, color: '#64748b', textTransform: 'uppercase' };
const td = { padding: '10px 8px', fontSize: 13 };
