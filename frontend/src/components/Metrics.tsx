import { useEffect, useState } from 'react'
import { getMetrics } from '../api'
import { MetricsResponse, MetricItem, LlmAgentUsage } from '../types'

// ── Design tokens ────────────────────────────────────────────────────────────
const C = {
  bg:       '#0a0f1e',
  surface:  '#111827',
  border:   '#1f2937',
  borderHi: '#374151',
  text:     '#f9fafb',
  textMid:  '#9ca3af',
  textLow:  '#4b5563',
  green:    '#10b981',
  greenBg:  '#052e16',
  greenBd:  '#065f46',
  amber:    '#f59e0b',
  amberBg:  '#1c1200',
  amberBd:  '#92400e',
  red:      '#ef4444',
  redBg:    '#1c0a0a',
  redBd:    '#7f1d1d',
  blue:     '#3b82f6',
  purple:   '#8b5cf6',
  indigo:   '#6366f1',
}

const STATUS = {
  green:  { color: C.green,  bg: C.greenBg, border: C.greenBd,  label: 'Passing' },
  yellow: { color: C.amber,  bg: C.amberBg, border: C.amberBd,  label: 'Warning' },
  red:    { color: C.red,    bg: C.redBg,   border: C.redBd,    label: 'Failing' },
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtCost(v: number) {
  if (v === 0) return '$0.0000'
  if (v < 0.001) return `$${v.toFixed(6)}`
  return `$${v.toFixed(4)}`
}
function fmtNum(v: number) { return v.toLocaleString() }
function fmtMs(v: number) { return `${v.toFixed(0)} ms` }

// ── Sub-components ────────────────────────────────────────────────────────────

function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <h2 style={{ margin: 0, fontSize: 13, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: C.textMid }}>{title}</h2>
      {subtitle && <p style={{ margin: '4px 0 0', fontSize: 12, color: C.textLow }}>{subtitle}</p>}
    </div>
  )
}

function KpiCard({ label, value, sub, color, icon }: { label: string; value: string; sub?: string; color: string; icon: string }) {
  return (
    <div style={{ backgroundColor: C.surface, borderRadius: 12, padding: '20px 22px', border: `1px solid ${C.border}`, position: 'relative', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, backgroundColor: color, borderRadius: '12px 12px 0 0' }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', color: C.textLow, marginBottom: 8 }}>{label}</div>
          <div style={{ fontSize: 28, fontWeight: 800, color, lineHeight: 1, letterSpacing: '-0.02em' }}>{value}</div>
          {sub && <div style={{ fontSize: 11, color: C.textLow, marginTop: 6 }}>{sub}</div>}
        </div>
        <div style={{ fontSize: 22, opacity: 0.6 }}>{icon}</div>
      </div>
    </div>
  )
}

function AgentRow({ a }: { a: LlmAgentUsage }) {
  const pct = Math.min(100, (a.cost_usd / 0.01) * 100)
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr 80px 90px 80px', alignItems: 'center', gap: 16, padding: '10px 16px', borderRadius: 8, backgroundColor: C.bg, border: `1px solid ${C.border}` }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: C.text, textTransform: 'capitalize' }}>{a.agent.replace(/_/g, ' ')}</div>
      <div style={{ height: 4, backgroundColor: C.border, borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, backgroundColor: C.indigo, borderRadius: 2, transition: 'width 0.4s ease' }} />
      </div>
      <div style={{ fontSize: 12, color: C.textMid, textAlign: 'right' }}>{fmtNum(a.calls)} calls</div>
      <div style={{ fontSize: 12, color: C.textMid, textAlign: 'right' }}>{fmtNum(a.tokens)} tok</div>
      <div style={{ fontSize: 12, fontWeight: 600, color: C.green, textAlign: 'right' }}>{fmtCost(a.cost_usd)}</div>
    </div>
  )
}

function QualityCard({ metric }: { metric: MetricItem }) {
  const cfg = STATUS[metric.status]
  const pct = Math.min(100, (metric.value / Math.max(metric.baseline, 1)) * 100)
  return (
    <div style={{ backgroundColor: C.surface, borderRadius: 12, padding: 20, border: `1px solid ${C.border}`, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1, paddingRight: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: C.textMid, marginBottom: 2 }}>{metric.label}</div>
          <div style={{ fontSize: 11, color: C.textLow, lineHeight: 1.5 }}>{metric.description}</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          <div style={{ width: 7, height: 7, borderRadius: '50%', backgroundColor: cfg.color, boxShadow: `0 0 8px ${cfg.color}` }} />
          <span style={{ fontSize: 11, fontWeight: 700, color: cfg.color, letterSpacing: '0.04em' }}>{cfg.label}</span>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span style={{ fontSize: 32, fontWeight: 800, color: cfg.color, lineHeight: 1, letterSpacing: '-0.02em' }}>{metric.value}</span>
        <span style={{ fontSize: 14, color: C.textLow }}>{metric.unit}</span>
        <span style={{ fontSize: 11, color: C.textLow, marginLeft: 4 }}>/ {metric.baseline}{metric.unit} target</span>
      </div>

      <div>
        <div style={{ height: 6, backgroundColor: C.bg, borderRadius: 3, overflow: 'hidden', position: 'relative' }}>
          <div style={{ position: 'absolute', left: `${metric.baseline}%`, top: 0, bottom: 0, width: 1, backgroundColor: C.borderHi, zIndex: 1 }} />
          <div style={{ height: '100%', width: `${pct}%`, backgroundColor: cfg.color, borderRadius: 3, transition: 'width 0.5s ease', opacity: 0.9 }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: 10, color: C.textLow }}>
          <span>0%</span>
          <span>target {metric.baseline}%</span>
          <span>100%</span>
        </div>
      </div>

      <div style={{ fontSize: 11, color: C.textLow, padding: '6px 10px', backgroundColor: C.bg, borderRadius: 6, border: `1px solid ${C.border}` }}>{metric.detail}</div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function Metrics() {
  const [data, setData] = useState<MetricsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function load() {
    setLoading(true)
    setError('')
    try { setData(await getMetrics()) }
    catch (e: any) { setError(e?.response?.data?.error || 'Failed to load metrics') }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const passing = data?.summary?.passing_metrics ?? 0
  const total   = data?.metrics?.length ?? 5
  const healthPct = total > 0 ? Math.round((passing / total) * 100) : 0
  const healthColor = healthPct >= 80 ? C.green : healthPct >= 60 ? C.amber : C.red
  const llm = data?.llm_usage
  const agents = data?.llm_usage_by_agent ?? []
  const computedAt = data?.computed_at
    ? new Date(data.computed_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : null

  return (
    <div style={{ fontFamily: "'Inter', system-ui, sans-serif", color: C.text }}>

      {/* Page header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 32 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, letterSpacing: '-0.02em', color: C.text }}>AI Quality Metrics</h1>
          <p style={{ margin: '6px 0 0', fontSize: 13, color: C.textMid }}>Measurable quality baselines · Evaluation framework · LLM cost tracking</p>
          {computedAt && <p style={{ margin: '4px 0 0', fontSize: 11, color: C.textLow }}>Last computed {computedAt}</p>}
        </div>
        <button
          onClick={load}
          disabled={loading}
          style={{ padding: '9px 18px', borderRadius: 8, border: `1px solid ${C.borderHi}`, backgroundColor: loading ? C.surface : C.bg, color: loading ? C.textLow : C.green, fontSize: 12, fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer', letterSpacing: '0.04em', display: 'flex', alignItems: 'center', gap: 7, transition: 'all 0.15s' }}
        >
          <span style={{ display: 'inline-block', animation: loading ? 'spin 1s linear infinite' : 'none', fontSize: 14 }}>⟳</span>
          {loading ? 'Computing…' : 'Refresh'}
        </button>
      </div>

      {error && (
        <div style={{ padding: '12px 16px', borderRadius: 8, backgroundColor: C.redBg, border: `1px solid ${C.redBd}`, color: C.red, fontSize: 13, marginBottom: 24 }}>{error}</div>
      )}

      {loading && !data && (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 200, color: C.textLow, fontSize: 14, gap: 10 }}>
          <span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>⟳</span> Computing metrics…
        </div>
      )}

      {data && (
        <>
          {/* ── Section 1: LLM Usage & Cost ─────────────────────────────── */}
          <div style={{ marginBottom: 36 }}>
            <SectionHeader title="LLM Usage & Cost Tracking" subtitle="Token consumption, latency, and estimated cost per agent" />

            {llm && llm.total_calls > 0 ? (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 20 }}>
                  <KpiCard label="Total API Calls"   value={fmtNum(llm.total_calls)}          sub="since account creation"  color={C.blue}   icon="🔁" />
                  <KpiCard label="Total Tokens"       value={fmtNum(llm.total_tokens)}         sub="prompt + completion"     color={C.purple} icon="🔤" />
                  <KpiCard label="Estimated Cost"     value={fmtCost(llm.total_cost_usd)}      sub="Cerebras / Bedrock"      color={C.green}  icon="💰" />
                  <KpiCard label="Avg Latency"        value={fmtMs(llm.avg_latency_ms)}        sub={`max ${fmtMs(llm.max_latency_ms)}`} color={C.amber} icon="⚡" />
                </div>

                {agents.length > 0 && (
                  <div style={{ backgroundColor: C.surface, borderRadius: 12, padding: 20, border: `1px solid ${C.border}` }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr 80px 90px 80px', gap: 16, padding: '0 16px 10px', borderBottom: `1px solid ${C.border}`, marginBottom: 10 }}>
                      {['Agent', 'Cost share', 'Calls', 'Tokens', 'Cost'].map(h => (
                        <div key={h} style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: C.textLow, textAlign: h === 'Agent' ? 'left' : 'right' }}>{h}</div>
                      ))}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {agents.map(a => <AgentRow key={a.agent} a={a} />)}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div style={{ backgroundColor: C.surface, borderRadius: 12, padding: 32, border: `1px solid ${C.border}`, textAlign: 'center' }}>
                <div style={{ fontSize: 28, marginBottom: 10 }}>🤖</div>
                <div style={{ fontSize: 14, color: C.textMid, marginBottom: 4 }}>No LLM calls recorded yet</div>
                <div style={{ fontSize: 12, color: C.textLow }}>Add an expense or ask an insights question to start tracking usage</div>
              </div>
            )}
          </div>

          {/* ── Section 2: Quality Baselines ────────────────────────────── */}
          <div style={{ marginBottom: 28 }}>
            <SectionHeader title="Quality Baselines" subtitle="Automated evaluation scores vs defined targets" />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 14 }}>
              {data.metrics.map(m => <QualityCard key={m.id} metric={m} />)}
            </div>
          </div>

          {/* ── Section 3: System Health ─────────────────────────────────── */}
          <div style={{ backgroundColor: C.surface, borderRadius: 12, padding: '18px 22px', border: `1px solid ${C.border}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <div style={{ width: 52, height: 52, borderRadius: '50%', border: `3px solid ${healthColor}`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, boxShadow: `0 0 16px ${healthColor}33` }}>
                <span style={{ fontSize: 15, fontWeight: 800, color: healthColor }}>{healthPct}%</span>
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: C.text }}>{passing}/{total} metrics passing baseline</div>
                <div style={{ fontSize: 12, color: C.textMid, marginTop: 2 }}>
                  System health: <span style={{ color: healthColor, fontWeight: 700 }}>{healthPct >= 80 ? 'Good' : healthPct >= 60 ? 'Needs Attention' : 'Critical'}</span>
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 24 }}>
              {[
                { label: 'Income entries', value: data.summary?.total_income_entries ?? 0 },
                { label: 'Expense entries', value: data.summary?.total_expense_entries ?? 0 },
                { label: 'Goals tracked', value: data.summary?.total_goals ?? 0 },
              ].map(s => (
                <div key={s.label} style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 20, fontWeight: 800, color: C.text }}>{s.value}</div>
                  <div style={{ fontSize: 11, color: C.textLow, marginTop: 2 }}>{s.label}</div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
