import React, { useEffect, useState } from 'react'
import { getMetrics } from '../api'
import { MetricsResponse, MetricItem } from '../types'

const STATUS_CONFIG = {
  green:  { color: '#10b981', bg: '#052e16', border: '#10b98133', label: 'Passing',  dot: '#10b981' },
  yellow: { color: '#f59e0b', bg: '#1c1200', border: '#f59e0b33', label: 'Warning',  dot: '#f59e0b' },
  red:    { color: '#f43f5e', bg: '#1c0a0a', border: '#f43f5e33', label: 'Failing',  dot: '#f43f5e' },
}

function ProgressBar({ value, baseline, status }: { value: number; baseline: number; status: MetricItem['status'] }) {
  const pct = Math.min((value / Math.max(baseline, 1)) * 100, 100)
  const cfg = STATUS_CONFIG[status]
  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#64748b', marginBottom: 4 }}>
        <span>0%</span>
        <span style={{ color: '#475569' }}>baseline {baseline}%</span>
        <span>100%</span>
      </div>
      <div style={{ height: 8, backgroundColor: '#334155', borderRadius: 4, overflow: 'hidden', position: 'relative' }}>
        {/* Baseline marker */}
        <div style={{ position: 'absolute', left: `${baseline}%`, top: 0, bottom: 0, width: 2, backgroundColor: '#475569', zIndex: 1 }} />
        {/* Value bar */}
        <div style={{ height: '100%', backgroundColor: cfg.color, width: `${pct}%`, borderRadius: 4, transition: 'width 0.5s ease', opacity: 0.9 }} />
      </div>
    </div>
  )
}

function MetricCard({ metric }: { metric: MetricItem }) {
  const cfg = STATUS_CONFIG[metric.status]
  return (
    <div style={{ backgroundColor: '#1e293b', borderRadius: 12, padding: 24, border: `1px solid ${cfg.border}`, position: 'relative', overflow: 'hidden' }}>
      {/* Status stripe */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 3, backgroundColor: cfg.color, borderRadius: '12px 12px 0 0' }} />

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div style={{ flex: 1, paddingRight: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#94a3b8', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            {metric.label}
          </div>
          <div style={{ fontSize: 11, color: '#475569', lineHeight: 1.4 }}>{metric.description}</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: cfg.dot, boxShadow: `0 0 6px ${cfg.dot}` }} />
          <span style={{ fontSize: 11, color: cfg.color, fontWeight: 600 }}>{cfg.label}</span>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4 }}>
        <span style={{ fontSize: 36, fontWeight: 800, color: cfg.color, lineHeight: 1 }}>{metric.value}</span>
        <span style={{ fontSize: 16, color: '#64748b', fontWeight: 500 }}>{metric.unit}</span>
        <span style={{ fontSize: 12, color: '#475569', marginLeft: 4 }}>/ {metric.baseline}{metric.unit} target</span>
      </div>

      <ProgressBar value={metric.value} baseline={metric.baseline} status={metric.status} />

      <div style={{ marginTop: 10, fontSize: 12, color: '#64748b', padding: '6px 10px', backgroundColor: '#0f172a', borderRadius: 6 }}>
        {metric.detail}
      </div>
    </div>
  )
}

export default function Metrics() {
  const [data, setData] = useState<MetricsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function load() {
    setLoading(true)
    setError('')
    try {
      const result = await getMetrics()
      setData(result)
    } catch (err: any) {
      setError(err?.response?.data?.error || 'Failed to load metrics.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const passing = data?.summary?.passing_metrics ?? 0
  const total = data?.metrics?.length ?? 5
  const healthPct = total > 0 ? Math.round((passing / total) * 100) : 0
  const healthColor = healthPct >= 80 ? '#10b981' : healthPct >= 60 ? '#f59e0b' : '#f43f5e'

  const computedAt = data?.computed_at
    ? new Date(data.computed_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : null

  const hasData = data && (
    (data.summary?.total_income_entries ?? 0) > 0 ||
    (data.summary?.total_expense_entries ?? 0) > 0
  )

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: '0 0 4px', color: '#f1f5f9' }}>AI Quality Metrics</h1>
          <p style={{ margin: 0, fontSize: 13, color: '#64748b' }}>Measurable quality baselines for evaluation framework</p>
          {computedAt && (
            <p style={{ margin: '6px 0 0', fontSize: 12, color: '#475569' }}>
              Last computed: <span style={{ color: '#64748b' }}>{computedAt}</span>
            </p>
          )}
        </div>
        <button
          onClick={load}
          disabled={loading}
          style={{ padding: '10px 20px', borderRadius: 8, border: '1px solid #334155', backgroundColor: loading ? '#1e293b' : '#0f172a', color: loading ? '#475569' : '#10b981', fontSize: 13, cursor: loading ? 'not-allowed' : 'pointer', fontWeight: 500, display: 'flex', alignItems: 'center', gap: 8, transition: 'all 0.15s' }}
        >
          <span style={{ display: 'inline-block', animation: loading ? 'spin 1s linear infinite' : 'none' }}>⟳</span>
          {loading ? 'Computing...' : 'Refresh Metrics'}
        </button>
      </div>

      {error && (
        <div style={{ padding: '12px 16px', borderRadius: 8, backgroundColor: '#1c0a0a', border: '1px solid #f43f5e33', color: '#f43f5e', fontSize: 13, marginBottom: 20 }}>
          {error}
        </div>
      )}

      {loading && !data && (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 200, color: '#475569', fontSize: 14 }}>
          <span style={{ marginRight: 10, display: 'inline-block', animation: 'spin 1s linear infinite' }}>⟳</span>
          Computing metrics...
        </div>
      )}

      {!loading && !data && !error && (
        <div style={{ backgroundColor: '#1e293b', borderRadius: 12, padding: 48, border: '1px solid #334155', textAlign: 'center' }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>📈</div>
          <div style={{ fontSize: 15, color: '#94a3b8', marginBottom: 6 }}>Add income and expenses to compute quality metrics</div>
          <div style={{ fontSize: 13, color: '#475569' }}>Metrics evaluate AI categorization, data completeness, and goal prediction quality</div>
        </div>
      )}

      {data && !hasData && (
        <div style={{ backgroundColor: '#1e293b', borderRadius: 12, padding: 32, border: '1px solid #334155', textAlign: 'center', marginBottom: 24 }}>
          <div style={{ fontSize: 24, marginBottom: 8 }}>📊</div>
          <div style={{ fontSize: 14, color: '#94a3b8' }}>Add income and expenses to compute quality metrics</div>
        </div>
      )}

      {data && data.metrics && data.metrics.length > 0 && (
        <>
          {/* Metric cards grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16, marginBottom: 24 }}>
            {data.metrics.map(metric => (
              <MetricCard key={metric.id} metric={metric} />
            ))}
          </div>

          {/* Summary row */}
          <div style={{ backgroundColor: '#1e293b', borderRadius: 12, padding: 20, border: '1px solid #334155', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <div style={{ width: 48, height: 48, borderRadius: '50%', border: `3px solid ${healthColor}`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <span style={{ fontSize: 14, fontWeight: 800, color: healthColor }}>{healthPct}%</span>
              </div>
              <div>
                <div style={{ fontSize: 15, fontWeight: 600, color: '#f1f5f9' }}>
                  {passing}/{total} metrics passing baseline
                </div>
                <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>
                  Overall system health: <span style={{ color: healthColor, fontWeight: 600 }}>{healthPct >= 80 ? 'Good' : healthPct >= 60 ? 'Needs Attention' : 'Critical'}</span>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: 20, fontSize: 12, color: '#64748b' }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 18, fontWeight: 700, color: '#f1f5f9' }}>{data.summary?.total_income_entries ?? 0}</div>
                <div>Income entries</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 18, fontWeight: 700, color: '#f1f5f9' }}>{data.summary?.total_expense_entries ?? 0}</div>
                <div>Expense entries</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 18, fontWeight: 700, color: '#f1f5f9' }}>{data.summary?.total_goals ?? 0}</div>
                <div>Goals tracked</div>
              </div>
            </div>
          </div>
        </>
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
