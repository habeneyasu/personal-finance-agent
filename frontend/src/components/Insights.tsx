import { useState, useRef, useEffect, useCallback } from 'react'
import { queryInsights } from '../api'
import type { InsightMessage } from '../types'

function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
}

const SUGGESTIONS = [
  { icon: '📊', text: 'How much did I spend this month?' },
  { icon: '🏆', text: 'What is my biggest expense category?' },
  { icon: '🎯', text: 'Am I on track to meet my savings goals?' },
  { icon: '💰', text: 'What is my net savings rate?' },
]

function SendIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  )
}

function SparkleIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2L13.09 8.26L19 6L14.74 10.91L21 12L14.74 13.09L19 18L13.09 15.74L12 22L10.91 15.74L5 18L9.26 13.09L3 12L9.26 10.91L5 6L10.91 8.26L12 2Z"/>
    </svg>
  )
}

export default function Insights() {
  const [messages, setMessages] = useState<InsightMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const send = useCallback(async (question: string) => {
    const q = question.trim()
    if (!q || loading) return

    setMessages(prev => [...prev, {
      role: 'user',
      content: q,
      timestamp: new Date().toISOString(),
    }])
    setInput('')
    setLoading(true)

    try {
      const data = await queryInsights(q)
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.answer || 'No response received.',
        timestamp: data.generated_at || new Date().toISOString(),
      }])
    } catch {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'I was unable to process your query at this time. Please try again.',
        timestamp: new Date().toISOString(),
      }])
    } finally {
      setLoading(false)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [loading])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    send(input)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  const isEmpty = messages.length === 0 && !loading

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 180px)', minHeight: '560px' }}>

      {/* Page Header */}
      <div style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
          <div style={{
            width: '32px', height: '32px', borderRadius: '8px',
            backgroundColor: '#0d2d1f', border: '1px solid #065f46',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#10b981',
          }}>
            <SparkleIcon />
          </div>
          <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#f1f5f9', margin: 0 }}>
            AI Financial Insights
          </h2>
          <span style={{
            fontSize: '11px', padding: '2px 8px', borderRadius: '20px',
            backgroundColor: '#0d2d1f', color: '#10b981',
            border: '1px solid #065f46', fontWeight: 500,
          }}>
            Powered by Bedrock
          </span>
        </div>
        <p style={{ fontSize: '13px', color: '#64748b', margin: 0, paddingLeft: '42px' }}>
          Ask natural language questions about your income, expenses, and savings goals
        </p>
      </div>

      {/* Chat Container */}
      <div style={{
        flex: 1,
        borderRadius: '16px',
        border: '1px solid #1e293b',
        backgroundColor: '#0f172a',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}>

        {/* Messages Area */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '24px',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}>

          {/* Empty State */}
          {isEmpty && (
            <div style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '32px',
              padding: '40px 0',
            }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{
                  width: '56px', height: '56px', borderRadius: '16px',
                  backgroundColor: '#0d2d1f', border: '1px solid #065f46',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  margin: '0 auto 16px',
                  color: '#10b981', fontSize: '24px',
                }}>
                  <SparkleIcon />
                </div>
                <p style={{ fontSize: '16px', fontWeight: 600, color: '#f1f5f9', margin: '0 0 6px' }}>
                  Ask about your finances
                </p>
                <p style={{ fontSize: '13px', color: '#475569', margin: 0 }}>
                  Get instant AI-powered insights from your financial data
                </p>
              </div>

              {/* Suggestion Pills */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '10px',
                width: '100%',
                maxWidth: '560px',
              }}>
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s.text}
                    onClick={() => send(s.text)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      padding: '12px 16px',
                      borderRadius: '12px',
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      color: '#94a3b8',
                      fontSize: '13px',
                      textAlign: 'left',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      lineHeight: '1.4',
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.borderColor = '#10b981'
                      e.currentTarget.style.color = '#e2e8f0'
                      e.currentTarget.style.backgroundColor = '#0d2d1f'
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.borderColor = '#334155'
                      e.currentTarget.style.color = '#94a3b8'
                      e.currentTarget.style.backgroundColor = '#1e293b'
                    }}
                  >
                    <span style={{ fontSize: '18px', flexShrink: 0 }}>{s.icon}</span>
                    <span>{s.text}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Message Bubbles */}
          {messages.map((msg, i) => (
            <div
              key={i}
              style={{
                display: 'flex',
                justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                alignItems: 'flex-end',
                gap: '10px',
              }}
            >
              {/* AI Avatar */}
              {msg.role === 'assistant' && (
                <div style={{
                  width: '28px', height: '28px', borderRadius: '8px', flexShrink: 0,
                  backgroundColor: '#0d2d1f', border: '1px solid #065f46',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: '#10b981',
                }}>
                  <SparkleIcon />
                </div>
              )}

              <div style={{
                maxWidth: '68%',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
                alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
              }}>
                {/* Label */}
                <span style={{ fontSize: '11px', color: '#475569', fontWeight: 500 }}>
                  {msg.role === 'user' ? 'You' : 'AI Assistant'}
                </span>

                {/* Bubble */}
                <div style={
                  msg.role === 'user'
                    ? {
                        padding: '12px 16px',
                        borderRadius: '16px 16px 4px 16px',
                        backgroundColor: '#1e40af',
                        color: '#e0e7ff',
                        fontSize: '14px',
                        lineHeight: '1.6',
                      }
                    : {
                        padding: '14px 18px',
                        borderRadius: '16px 16px 16px 4px',
                        backgroundColor: '#1e293b',
                        border: '1px solid #334155',
                        color: '#e2e8f0',
                        fontSize: '14px',
                        lineHeight: '1.7',
                        whiteSpace: 'pre-wrap',
                      }
                }>
                  {msg.content}
                </div>

                {/* Timestamp */}
                <span style={{ fontSize: '11px', color: '#334155' }}>
                  {fmtTime(msg.timestamp)}
                </span>
              </div>

              {/* User Avatar */}
              {msg.role === 'user' && (
                <div style={{
                  width: '28px', height: '28px', borderRadius: '8px', flexShrink: 0,
                  backgroundColor: '#1e3a8a', border: '1px solid #1d4ed8',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: '#93c5fd', fontSize: '12px', fontWeight: 600,
                }}>
                  U
                </div>
              )}
            </div>
          ))}

          {/* Thinking Indicator */}
          {loading && (
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: '10px' }}>
              <div style={{
                width: '28px', height: '28px', borderRadius: '8px', flexShrink: 0,
                backgroundColor: '#0d2d1f', border: '1px solid #065f46',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: '#10b981',
              }}>
                <SparkleIcon />
              </div>
              <div style={{
                padding: '14px 18px',
                borderRadius: '16px 16px 16px 4px',
                backgroundColor: '#1e293b',
                border: '1px solid #334155',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}>
                <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                  {[0, 1, 2].map(i => (
                    <div
                      key={i}
                      style={{
                        width: '6px', height: '6px', borderRadius: '50%',
                        backgroundColor: '#10b981',
                        animation: 'bounce 1.2s infinite',
                        animationDelay: `${i * 0.2}s`,
                      }}
                    />
                  ))}
                </div>
                <span style={{ fontSize: '13px', color: '#64748b' }}>Analyzing your finances...</span>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Divider */}
        <div style={{ height: '1px', backgroundColor: '#1e293b' }} />

        {/* Input Area */}
        <div style={{ padding: '16px 20px', backgroundColor: '#0f172a' }}>
          <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your finances..."
              disabled={loading}
              autoFocus
              style={{
                flex: 1,
                padding: '12px 16px',
                borderRadius: '12px',
                backgroundColor: '#1e293b',
                border: '1px solid #334155',
                color: '#e2e8f0',
                fontSize: '14px',
                outline: 'none',
                transition: 'border-color 0.15s',
              }}
              onFocus={e => e.currentTarget.style.borderColor = '#10b981'}
              onBlur={e => e.currentTarget.style.borderColor = '#334155'}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              style={{
                width: '44px', height: '44px',
                borderRadius: '12px',
                backgroundColor: input.trim() && !loading ? '#10b981' : '#1e293b',
                border: `1px solid ${input.trim() && !loading ? '#10b981' : '#334155'}`,
                color: input.trim() && !loading ? '#0f172a' : '#475569',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                cursor: input.trim() && !loading ? 'pointer' : 'not-allowed',
                transition: 'all 0.15s ease',
                flexShrink: 0,
              }}
            >
              <SendIcon />
            </button>
          </form>
          <p style={{ fontSize: '11px', color: '#334155', margin: '8px 0 0', textAlign: 'center' }}>
            Press Enter to send · Powered by AWS Bedrock
          </p>
        </div>
      </div>

      <style>{`
        @keyframes bounce {
          0%, 60%, 100% { transform: translateY(0); }
          30% { transform: translateY(-6px); }
        }
      `}</style>
    </div>
  )
}
