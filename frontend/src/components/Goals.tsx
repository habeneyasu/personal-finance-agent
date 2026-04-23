import { useEffect, useState } from 'react'
import { getGoals, createGoal } from '../api'
import type { SavingsGoal } from '../types'

function fmt(n: number) {
  return Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtDate(d: string) {
  return new Date(d + 'T00:00:00').toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  })
}

function tomorrow() {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  return d.toISOString().split('T')[0]
}

interface GoalCardProps {
  goal: SavingsGoal
}

function GoalCard({ goal }: GoalCardProps) {
  const pct = Math.min(100, Math.max(0, goal.progress_pct ?? 0))
  const remaining = Math.max(0, Number(goal.target_amount) - Number(goal.current_amount))

  return (
    <div
      className="rounded-xl p-5 flex flex-col gap-4"
      style={{ backgroundColor: '#1e293b', border: '1px solid #334155' }}
    >
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-base font-semibold" style={{ color: '#f1f5f9' }}>{goal.name}</h3>
          <p className="text-xs mt-0.5" style={{ color: '#64748b' }}>
            Target: {fmtDate(goal.target_date)}
          </p>
        </div>
        <span
          className="text-xs px-2 py-1 rounded-full font-medium"
          style={{
            backgroundColor: pct >= 100 ? '#0f2d1f' : '#1e293b',
            color: pct >= 100 ? '#10b981' : '#94a3b8',
            border: `1px solid ${pct >= 100 ? '#065f46' : '#334155'}`,
          }}
        >
          {pct >= 100 ? '✓ Complete' : `${pct.toFixed(1)}%`}
        </span>
      </div>

      {/* Progress Bar */}
      <div>
        <div className="flex justify-between text-xs mb-1.5" style={{ color: '#64748b' }}>
          <span>${fmt(Number(goal.current_amount))}</span>
          <span>${fmt(Number(goal.target_amount))}</span>
        </div>
        <div className="rounded-full h-2" style={{ backgroundColor: '#0f172a' }}>
          <div
            className="rounded-full h-2 transition-all duration-500"
            style={{
              width: `${pct}%`,
              backgroundColor: pct >= 100 ? '#10b981' : '#10b981',
              opacity: pct >= 100 ? 1 : 0.85,
            }}
          />
        </div>
      </div>

      <div className="flex items-center justify-between text-xs">
        <span style={{ color: '#64748b' }}>
          ${fmt(remaining)} remaining
        </span>
        {goal.predicted_completion_date ? (
          <span style={{ color: '#94a3b8' }}>
            Est. {fmtDate(goal.predicted_completion_date)}
          </span>
        ) : (
          <span style={{ color: '#475569' }}>No prediction yet</span>
        )}
      </div>
    </div>
  )
}

export default function Goals() {
  const [goals, setGoals] = useState<SavingsGoal[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [flash, setFlash] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({ name: '', target_amount: '', target_date: tomorrow() })

  const load = async () => {
    try {
      const data = await getGoals()
      setGoals(data)
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    const amount = parseFloat(form.target_amount)
    if (!amount || amount <= 0) { setError('Target amount must be greater than 0'); return }
    if (!form.name.trim()) { setError('Goal name is required'); return }
    setSubmitting(true)
    try {
      await createGoal({
        name: form.name.trim(),
        target_amount: amount,
        target_date: form.target_date,
      })
      setForm({ name: '', target_amount: '', target_date: tomorrow() })
      setShowForm(false)
      setFlash(true)
      setTimeout(() => setFlash(false), 2000)
      await load()
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || 'Failed to create goal'
      setError(detail)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold" style={{ color: '#f1f5f9' }}>Savings Goals</h2>
          <p className="text-sm" style={{ color: '#64748b' }}>
            {goals.length} goal{goals.length !== 1 ? 's' : ''} active
          </p>
        </div>
        <button
          onClick={() => { setShowForm(!showForm); setError(null) }}
          className="text-sm px-4 py-2 rounded-lg font-medium transition-colors"
          style={{ backgroundColor: '#0f2d1f', color: '#10b981', border: '1px solid #065f46' }}
        >
          {showForm ? 'Cancel' : '+ Add Goal'}
        </button>
      </div>

      {/* Add Goal Form */}
      {showForm && (
        <div
          className="rounded-xl p-5"
          style={{
            backgroundColor: '#1e293b',
            border: flash ? '1px solid #10b981' : '1px solid #334155',
            transition: 'border-color 0.3s',
          }}
        >
          <h3 className="text-sm font-semibold mb-4" style={{ color: '#94a3b8' }}>New Goal</h3>
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            {error && (
              <p className="text-xs" style={{ color: '#f43f5e' }}>{error}</p>
            )}
            <input
              type="text"
              placeholder="Goal name (e.g. Vacation Fund)"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="rounded-lg px-3 py-2 text-sm outline-none"
              style={{ backgroundColor: '#0f172a', border: '1px solid #334155', color: '#e2e8f0' }}
              required
            />
            <input
              type="number"
              step="0.01"
              placeholder="Target amount"
              value={form.target_amount}
              onChange={(e) => setForm({ ...form, target_amount: e.target.value })}
              className="rounded-lg px-3 py-2 text-sm outline-none"
              style={{ backgroundColor: '#0f172a', border: '1px solid #334155', color: '#e2e8f0' }}
              required
            />
            <div>
              <label className="text-xs mb-1 block" style={{ color: '#64748b' }}>Target date</label>
              <input
                type="date"
                value={form.target_date}
                onChange={(e) => setForm({ ...form, target_date: e.target.value })}
                className="rounded-lg px-3 py-2 text-sm outline-none w-full"
                style={{ backgroundColor: '#0f172a', border: '1px solid #334155', color: '#e2e8f0' }}
                required
              />
            </div>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg py-2 text-sm font-medium transition-opacity"
              style={{ backgroundColor: '#10b981', color: '#0f172a', opacity: submitting ? 0.6 : 1 }}
            >
              {submitting ? 'Creating...' : 'Create Goal'}
            </button>
          </form>
        </div>
      )}

      {/* Goals Grid */}
      {loading ? (
        <div className="flex items-center justify-center h-48">
          <div className="flex items-center gap-3 text-sm" style={{ color: '#64748b' }}>
            <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
            Loading goals...
          </div>
        </div>
      ) : goals.length === 0 ? (
        <div
          className="rounded-xl p-12 text-center"
          style={{ backgroundColor: '#1e293b', border: '1px solid #334155' }}
        >
          <p className="text-2xl mb-2">◎</p>
          <p className="text-sm font-medium" style={{ color: '#94a3b8' }}>No goals yet</p>
          <p className="text-xs mt-1" style={{ color: '#475569' }}>
            Create your first savings goal to start tracking progress
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {goals.map((g) => (
            <GoalCard key={g.id} goal={g} />
          ))}
        </div>
      )}
    </div>
  )
}
