import Link from 'next/link';
import { useRouter } from 'next/router';

export default function Layout({ children }) {
  const router = useRouter();

  async function logout() {
    await fetch('/api/auth/logout', { method: 'POST' });
    router.push('/login');
  }

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', minHeight: '100vh', background: '#f8fafc' }}>
      <nav style={nav.bar}>
        <span style={nav.brand}>MedHall Connect — Admin</span>
        <div style={{ display: 'flex', gap: 16 }}>
          <Link href="/" style={nav.link}>Dashboard</Link>
          <Link href="/users" style={nav.link}>Users</Link>
          <Link href="/reports" style={nav.link}>Reports</Link>
          <Link href="/sessions" style={nav.link}>Sessions</Link>
          <Link href="/audit" style={nav.link}>Audit Log</Link>
          <button onClick={logout} style={nav.logout}>Log out</button>
        </div>
      </nav>
      <main style={{ padding: 24, maxWidth: 1100, margin: '0 auto' }}>{children}</main>
    </div>
  );
}

const nav = {
  bar: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 24px', background: '#0f172a', color: '#fff' },
  brand: { fontWeight: 600 },
  link: { color: '#cbd5e1', textDecoration: 'none', fontSize: 14 },
  logout: { background: 'transparent', border: '1px solid #475569', color: '#fff', borderRadius: 6, padding: '4px 10px', cursor: 'pointer' },
};
