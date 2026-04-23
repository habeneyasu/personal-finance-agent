import { useState } from 'react'
import { login, register } from '../api'

interface Props { onLogin: (token: string, email: string) => void }

export default function Login({ onLogin }: Props) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = mode === 'login' ? await login(email, password) : await register(email, password)
      const token = data.token || data.access_token
      if (token) {
        onLogin(token, data.email || email)
      } else {
        setError('Unexpected response from server.')
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.response?.data?.error || 'Authentication failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#0f172a', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
      <div style={{ width: '100%', maxWidth: 420 }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 40 }}>
          <div style={{ fontSize: 36, fontWeight: 800, color: '#10b981', letterSpacing: -1 }}>PFIP</div>
          <div style={{ color: '#64748b', fontSize: 14, marginTop: 4 }}>Personal Finance Intelligence Platform</div>
        </div>

        {/* Card */}
        <div style={{ backgroundColor: '#1e293b', borderRadius: 16, padding: 32, border: '1px solid #334155' }}>
          <h2 style={{ margin: '0 0 24px', fontSize: 20, fontWeight: 600, color: '#f1f5f9' }}>
            {mode === 'login' ? 'Welcome back' : 'Create account'}
          </h2>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <label htmlFor="email" style={{ display: 'block', fontSize: 13, color: '#94a3b8', marginBottom: 6 }}>Email</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                required
                style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #334155', backgroundColor: '#0f172a', color: '#f1f5f9', fontSize: 14, outline: 'none', boxSizing: 'border-box' }}
              />
            </div>
            <div>
              <label htmlFor="password" style={{ display: 'block', fontSize: 13, color: '#94a3b8', marginBottom: 6 }}>Password</label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                required
                style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #334155', backgroundColor: '#0f172a', color: '#f1f5f9', fontSize: 14, outline: 'none', boxSizing: 'border-box' }}
              />
            </div>

            {error && (
              <div role="alert" style={{ padding: '10px 14px', borderRadius: 8, backgroundColor: '#1c0a0a', border: '1px solid #f43f5e', color: '#f43f5e', fontSize: 13 }}>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              style={{ padding: '12px', borderRadius: 8, border: 'none', backgroundColor: '#10b981', color: '#fff', fontSize: 15, fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.7 : 1, marginTop: 4 }}
            >
              {loading ? 'Please wait...' : mode === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>

          <div style={{ marginTop: 20, textAlign: 'center', fontSize: 13, color: '#64748b' }}>
            {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
            <button
              onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}
              style={{ background: 'none', border: 'none', color: '#10b981', cursor: 'pointer', fontSize: 13, fontWeight: 500 }}
            >
              {mode === 'login' ? 'Register' : 'Sign In'}
            </button>
          </div>
        </div>

        {/* Demo hint */}
        <div style={{ marginTop: 20, padding: '12px 16px', borderRadius: 10, backgroundColor: '#1e293b', border: '1px solid #334155', fontSize: 12, color: '#64748b', textAlign: 'center' }}>
          Demo credentials: <span style={{ color: '#94a3b8', fontFamily: 'monospace' }}>demo@pfip.dev</span> / <span style={{ color: '#94a3b8', fontFamily: 'monospace' }}>Demo1234!</span>
        </div>
      </div>
    </div>
  )
}
