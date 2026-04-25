import { useState } from 'react'
import Login from './components/Login'
import Overview from './components/Overview'
import Transactions from './components/Transactions'
import Goals from './components/Goals'
import Insights from './components/Insights'
import Metrics from './components/Metrics'

type Tab = 'overview' | 'transactions' | 'goals' | 'insights' | 'metrics'

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'overview',     label: 'Overview',      icon: '📊' },
  { id: 'transactions', label: 'Transactions',   icon: '💳' },
  { id: 'goals',        label: 'Goals',          icon: '🎯' },
  { id: 'insights',     label: 'Insights',       icon: '✨' },
  { id: 'metrics',      label: 'Metrics',        icon: '📈' },
]

export default function App() {
  const [token, setToken]       = useState<string | null>(localStorage.getItem('pfip_token'))
  const [email, setEmail]       = useState<string>(localStorage.getItem('pfip_email') || '')
  const [activeTab, setActiveTab] = useState<Tab>('overview')

  function handleLogin(t: string, e: string) {
    localStorage.setItem('pfip_token', t)
    localStorage.setItem('pfip_email', e)
    setToken(t)
    setEmail(e)
  }

  function handleSignOut() {
    localStorage.removeItem('pfip_token')
    localStorage.removeItem('pfip_email')
    setToken(null)
    setEmail('')
  }

  if (!token) return <Login onLogin={handleLogin} />

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#0f172a', color: '#f1f5f9' }}>
      {/* Header */}
      <header role="banner" style={{ backgroundColor: '#1e293b', borderBottom: '1px solid #334155' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 60, gap: 12 }}>
          {/* Logo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, backgroundColor: '#10b981', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, color: '#0f172a', fontSize: 14 }}>P</div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9', lineHeight: 1 }}>PFIP</div>
              <div style={{ fontSize: 11, color: '#64748b', lineHeight: 1 }}>Personal Finance</div>
            </div>
          </div>

          {/* Nav — scrollable on mobile */}
          <nav role="navigation" aria-label="Main navigation" className="nav-scroll" style={{ display: 'flex', gap: 2, overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
            {TABS.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                aria-current={activeTab === tab.id ? 'page' : undefined}
                aria-label={tab.label}
                style={{
                  padding: '7px 14px',
                  borderRadius: 8,
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: 13,
                  fontWeight: 500,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 5,
                  whiteSpace: 'nowrap',
                  backgroundColor: activeTab === tab.id ? '#10b981' : 'transparent',
                  color: activeTab === tab.id ? '#fff' : '#94a3b8',
                  transition: 'background-color 0.15s, color 0.15s',
                }}
              >
                <span aria-hidden="true">{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            ))}
          </nav>

          {/* User + sign out */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
            <span className="hide-mobile" style={{ fontSize: 12, color: '#64748b', maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{email}</span>
            <button
              onClick={handleSignOut}
              aria-label="Sign out"
              style={{ padding: '7px 14px', borderRadius: 8, border: '1px solid #334155', backgroundColor: 'transparent', color: '#94a3b8', cursor: 'pointer', fontSize: 13, whiteSpace: 'nowrap', transition: 'border-color 0.15s, color 0.15s' }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = '#f43f5e'; e.currentTarget.style.color = '#f43f5e' }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = '#334155'; e.currentTarget.style.color = '#94a3b8' }}
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main role="main" style={{ maxWidth: 1200, margin: '0 auto', padding: '28px 16px' }}>
        {activeTab === 'overview'     && <Overview />}
        {activeTab === 'transactions' && <Transactions />}
        {activeTab === 'goals'        && <Goals />}
        {activeTab === 'insights'     && <Insights />}
        {activeTab === 'metrics'      && <Metrics />}
      </main>
    </div>
  )
}
