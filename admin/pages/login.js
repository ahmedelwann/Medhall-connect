import { useState } from 'react';
import { useRouter } from 'next/router';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function onSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || 'Login failed');
        return;
      }
      router.push('/');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={styles.wrap}>
      <form onSubmit={onSubmit} style={styles.card}>
        <h1 style={styles.title}>MedHall Connect — Admin</h1>
        <input
          style={styles.input}
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoFocus
        />
        <input
          style={styles.input}
          placeholder="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && <p style={styles.error}>{error}</p>}
        <button style={styles.button} disabled={loading} type="submit">
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  );
}

const styles = {
  wrap: { display: 'flex', minHeight: '100vh', alignItems: 'center', justifyContent: 'center', background: '#0f172a', fontFamily: 'system-ui, sans-serif' },
  card: { background: '#fff', padding: 32, borderRadius: 12, width: 320, display: 'flex', flexDirection: 'column', gap: 12 },
  title: { fontSize: 18, marginBottom: 8 },
  input: { padding: 10, borderRadius: 8, border: '1px solid #cbd5e1' },
  button: { padding: 10, borderRadius: 8, border: 'none', background: '#2563eb', color: '#fff', cursor: 'pointer' },
  error: { color: '#dc2626', fontSize: 13 },
};
