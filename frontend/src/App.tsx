import { useState, useEffect } from 'react'
import Overview from './components/Overview'
import Transactions from './components/Transactions'
import Goals from './components/Goals'
import Insights from './components/Insights'
import Login from './components/Login'

type Tab = 'overview' | 'transactions' | 'goals' | 'insights'

// Professional tab configuration with proper icon descriptions
const TABS: { id: Tab; label: string; icon: string; description: string }[] = [
  { 
    id: 'overview', 
    label: 'Overview', 
    icon: 'Ø', 
    description: 'Financial dashboard and summary'
  },
  { 
    id: 'transactions', 
    label: 'Transactions', 
    icon: 'â', 
    description: 'Income and expense management'
  },
  { 
    id: 'goals', 
    label: 'Goals', 
    icon: 'â¡', 
    description: 'Savings goals and progress tracking'
  },
  { 
    id: 'insights', 
    label: 'Insights', 
    icon: 'â¦', 
    description: 'AI-powered financial insights'
  },
]

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('overview')
  const [token, setToken] = useState<string | null>(localStorage.getItem('pfip_token'))
  const [email, setEmail] = useState<string>(localStorage.getItem('pfip_email') || '')
  const [isMobile, setIsMobile] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Handle responsive behavior
  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth < 768)
      if (window.innerWidth >= 768) {
        setSidebarOpen(false)
      }
    }
    
    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const handleAuth = (newToken: string, newEmail: string) => {
    setToken(newToken)
    setEmail(newEmail)
    localStorage.setItem('pfip_token', newToken)
    localStorage.setItem('pfip_email', newEmail)
  }

  const handleLogout = () => {
    localStorage.removeItem('pfip_token')
    localStorage.removeItem('pfip_email')
    setToken(null)
    setEmail('')
  }

  if (!token) {
    return <Login onAuth={handleAuth} />
  }

  // Mobile sidebar component
  const MobileSidebar = () => (
    <div className={`fixed inset-0 z-50 ${sidebarOpen ? 'block' : 'hidden'}`}>
      <div 
        className="fixed inset-0 bg-black/50" 
        onClick={() => setSidebarOpen(false)}
      />
      <div className="fixed left-0 top-0 h-full w-64 bg-secondary-800 border-r border-secondary-700">
        <div className="p-4">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold bg-primary-600 text-secondary-900">
              P
            </div>
            <div>
              <h1 className="text-lg font-semibold text-secondary-100">PFIP</h1>
              <p className="text-xs text-secondary-400">Finance Intelligence</p>
            </div>
          </div>
          
          <nav className="space-y-1">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveTab(tab.id)
                  setSidebarOpen(false)
                }}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-200 ${
                  activeTab === tab.id
                    ? 'bg-primary-600 text-white'
                    : 'text-secondary-300 hover:bg-secondary-700 hover:text-secondary-100'
                }`}
                title={tab.description}
              >
                <span className="mr-3">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-secondary-900 text-secondary-100">
      {/* Mobile Sidebar */}
      {isMobile && <MobileSidebar />}

      {/* Header */}
      <header className="bg-secondary-800 border-b border-secondary-700 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Left side - Logo and mobile menu */}
            <div className="flex items-center gap-4">
              {isMobile && (
                <button
                  onClick={() => setSidebarOpen(true)}
                  className="p-2 rounded-lg text-secondary-400 hover:text-secondary-100 hover:bg-secondary-700 transition-colors duration-200"
                  aria-label="Open navigation menu"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                </button>
              )}
              
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold bg-primary-600 text-secondary-900">
                  P
                </div>
                <div>
                  <h1 className="text-base font-semibold text-secondary-100">PFIP</h1>
                  <p className="text-xs text-secondary-400 hidden sm:block">Finance Intelligence Platform</p>
                </div>
              </div>
            </div>

            {/* Right side - User info and logout */}
            <div className="flex items-center gap-4">
              <div className="hidden sm:block">
                <span className="text-sm text-secondary-400">{email}</span>
              </div>
              <button
                onClick={handleLogout}
                className="btn btn-ghost text-sm"
                title="Sign out"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                <span className="hidden sm:inline ml-2">Sign out</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Desktop Navigation */}
      {!isMobile && (
        <nav className="bg-secondary-800 border-b border-secondary-700">
          <div className="max-w-7xl mx-auto px-6">
            <div className="flex gap-1">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`nav-link px-4 py-3 text-sm font-medium transition-all duration-200 ${
                    activeTab === tab.id
                      ? 'nav-link-active'
                      : 'nav-link-inactive'
                  }`}
                  title={tab.description}
                >
                  <span className="mr-2">{tab.icon}</span>
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
        </nav>
      )}

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        <div className="animate-fade-in">
          {activeTab === 'overview' && <Overview />}
          {activeTab === 'transactions' && <Transactions />}
          {activeTab === 'goals' && <Goals />}
          {activeTab === 'insights' && <Insights />}
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-secondary-800 border-t border-secondary-700 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="text-center text-sm text-secondary-400">
            2026 PFIP. Built with AI-powered financial intelligence.
          </div>
        </div>
      </footer>
    </div>
  )
}
