import { useState, useRef, useEffect } from 'react'
import { queryInsights } from '../api'
import { InsightMessage } from '../types'

const SUGGESTIONS = [
  'How much did I spend last month?',
  'Am I on track with my savings goals?',
  'What is my biggest expense category?',
  'How can I improve my savings rate?',
]

export default function Insights() {
  const [messages, setMessages] = useState<InsightMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, loading])

  async function send(question: string) {
    if (!question.trim() || loading) return
    const userMsg: InsightMessage = { role: 'user', content: question, timestamp: new Date().toISOString() }
    setMessages(m => [...m, userMsg])
    setInput('')
    setLoading(true)
    try {
      const data = await queryInsights(question)
      const aiMsg: InsightMessage = {
        role: 'assistant',
        content: data.answer || data.response || data.message || JSON.stringify(data),
        timestamp: new Date().toISOString(),
        decision: data.decision,
        reason: data.reason,
        retried: data.retried,
        data_sources: data.data_sources,
      }
      setMessages(m => [...m, aiMsg])
    } catch {
      setMessages(m => [...m, { role: 'assistant', content: 'Sorry, I could not process your request. Please try again.', timestamp: new Date().toISOString() }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 200px)', minHeight: 500 }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 20, color: '#f1f5f9', flexShrink: 0 }}>AI Insights</h1>

      {/* Chat area */}
      <div style={{ flex: 1, backgroundColor: '#1e293b', borderRadius: 12, border: '1px solid #334155', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ flex: 1, overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>

          {messages.length === 0 && !loading && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, gap: 24 }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 32, marginBottom: 8 }}>✨</div>
                <div style={{ fontSize: 16, fontWeight: 600, color: '#f1f5f9', marginBottom: 4 }}>Ask about your finances</div>
                <div style={{ fontSize: 13, color: '#64748b' }}>Get AI-powered insights about your spending and savings</div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, width: '100%', maxWidth: 500 }}>
                {SUGGESTIONS.map(s => (
                  <button key={s} onClick={() => send(s)} style={{ padding: '12px 14px', borderRadius: 8, border: '1px solid #334155', backgroundColor: '#0f172a', color: '#94a3b8', fontSize: 12, cursor: 'pointer', textAlign: 'left', lineHeight: 1.4 }}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start', gap: 10 }}>
              {msg.role === 'assistant' && (
                <div style={{ width: 28, height: 28, borderRadius: '50%', backgroundColor: '#10b981', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, flexShrink: 0, marginTop: 2 }}>✨</div>
              )}
              <div style={{ maxWidth: '70%', display: 'flex', flexDirection: 'column', gap: 4 }}>
                <div style={{
                  padding: '12px 16px',
                  borderRadius: msg.role === 'user' ? '12px 12px 4px 12px' : '12px 12px 12px 4px',
                  backgroundColor: msg.role === 'user' ? '#3b82f6' : '#0f172a',
                  color: '#f1f5f9',
                  fontSize: 14,
                  lineHeight: 1.6,
                  border: msg.role === 'assistant' ? '1px solid #334155' : 'none',
                }}>
                  {msg.content}
                </div>
                {msg.role === 'assistant' && msg.decision && (() => {
                  const badges: Record<string, { label: string; color: string; bg: string }> = {
                    accept:    { label: '✓ Accepted',      color: '#10b981', bg: 'rgba(16,185,129,0.1)' },
                    retry:     { label: '↺ Accepted after retry', color: '#f59e0b', bg: 'rgba(245,158,11,0.1)' },
                    fallback:  { label: '⚡ SQL Fallback',  color: '#6366f1', bg: 'rgba(99,102,241,0.1)' },
                    sql_local: { label: '⚡ SQL (local)',   color: '#64748b', bg: 'rgba(100,116,139,0.1)' },
                  }
                  const b = badges[msg.decision] || { label: msg.decision, color: '#64748b', bg: 'transparent' }
                  return (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingLeft: 4, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 11, color: b.color, backgroundColor: b.bg, padding: '2px 8px', borderRadius: 4, border: `1px solid ${b.color}33` }}>
                        {b.label}
                      </span>
                      {msg.reason && msg.reason !== 'numbers_verified' && msg.reason !== 'no_llm_key' && (
                        <span style={{ fontSize: 11, color: '#475569' }}>{msg.reason.replace(/_/g, ' ')}</span>
                      )}
                      {msg.data_sources && msg.data_sources.length > 0 && (
                        <span style={{ fontSize: 11, color: '#334155', backgroundColor: '#0f172a', padding: '2px 8px', borderRadius: 4, border: '1px solid #1e293b' }}>
                          {msg.data_sources.map(s => s.replace('_agent', '')).join(' · ')}
                        </span>
                      )}
                    </div>
                  )
                })()}
              </div>
            </div>
          ))}

          {loading && (
            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
              <div style={{ width: 28, height: 28, borderRadius: '50%', backgroundColor: '#10b981', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, flexShrink: 0 }}>✨</div>
              <div style={{ padding: '12px 16px', borderRadius: '12px 12px 12px 4px', backgroundColor: '#0f172a', border: '1px solid #334155', display: 'flex', gap: 6, alignItems: 'center' }}>
                <span style={{ fontSize: 13, color: '#64748b' }}>Analyzing your finances</span>
                {[0, 1, 2].map(i => (
                  <span key={i} style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: '#10b981', display: 'inline-block', animation: `pulse 1.2s ${i * 0.2}s infinite` }} />
                ))}
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div style={{ padding: '16px 20px', borderTop: '1px solid #334155', display: 'flex', gap: 10 }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send(input)}
            placeholder="Ask about your finances..."
            style={{ flex: 1, padding: '10px 16px', borderRadius: 8, border: '1px solid #334155', backgroundColor: '#0f172a', color: '#f1f5f9', fontSize: 14, outline: 'none' }}
          />
          <button
            onClick={() => send(input)}
            disabled={loading || !input.trim()}
            aria-label="Send message"
            style={{ padding: '10px 18px', borderRadius: 8, border: 'none', backgroundColor: '#10b981', color: '#fff', cursor: loading || !input.trim() ? 'not-allowed' : 'pointer', opacity: loading || !input.trim() ? 0.5 : 1, fontSize: 16 }}
          >
            ➤
          </button>
        </div>
      </div>

      <style>{`@keyframes pulse { 0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); } 40% { opacity: 1; transform: scale(1); } }`}</style>
    </div>
  )
}
