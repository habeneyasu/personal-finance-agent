import { useEffect, useState } from 'react'
import { getIncome, getExpenses, createIncome, createExpense } from '../api'
import type { IncomeEntry, ExpenseEntry } from '../types'

function fmt(n: number) {
  return Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtDate(d: string) {
  return new Date(d + 'T00:00:00').toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  })
}

function today() {
  return new Date().toISOString().split('T')[0]
}

// ── Income Column ─────────────────────────────────────────────────────────────

function IncomeColumn() {
  const [entries, setEntries] = useState<IncomeEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [flash, setFlash] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({ amount: '', source: '', date: today(), notes: '' })

  const load = async () => {
    try {
      const data = await getIncome()
      setEntries(data)
    } catch {
      // silent on poll
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    const amount = parseFloat(form.amount)
    if (!amount || amount <= 0) { setError('Amount must be greater than 0'); return }
    if (!form.source.trim()) { setError('Source is required'); return }
    setSubmitting(true)
    try {
      await createIncome({
        amount,
        source: form.source.trim(),
        date: form.date,
        notes: form.notes.trim() || undefined,
      })
      setForm({ amount: '', source: '', date: today(), notes: '' })
      setShowForm(false)
      setFlash(true)
      setTimeout(() => setFlash(false), 2000)
      await load()
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || 'Failed to add income'
      setError(detail)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      className="rounded-xl p-5 flex flex-col gap-4"
      style={{
        backgroundColor: '#1e293b',
        border: flash ? '1px solid #10b981' : '1px solid #334155',
        transition: 'border-color 0.3s',
      }}
    >
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold" style={{ color: '#10b981' }}>
          ↑ Income
        </h2>
        <button
          onClick={() => { setShowForm(!showForm); setError(null) }}
          className="text-xs px-3 py-1.5 rounded-lg font-medium transition-colors"
          style={{ backgroundColor: '#0f2d1f', color: '#10b981', border: '1px solid #065f46' }}
        >
          {showForm ? 'Cancel' : '+ Add'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          {error && (
            <p className="text-xs" style={{ color: '#f43f5e' }}>{error}</p>
          )}
          <input
            type="number"
            step="0.01"
            placeholder="Amount"
            value={form.amount}
            onChange={(e) => setForm({ ...form, amount: e.target.value })}
            className="rounded-lg px-3 py-2 text-sm outline-none"
            style={{ backgroundColor: '#0f172a', border: '1px solid #334155', color: '#e2e8f0' }}
            required
          />
          <input
            type="text"
            placeholder="Source (e.g. Salary, Freelance)"
            value={form.source}
            onChange={(e) => setForm({ ...form, source: e.target.value })}
            className="rounded-lg px-3 py-2 text-sm outline-none"
            style={{ backgroundColor: '#0f172a', border: '1px solid #334155', color: '#e2e8f0' }}
            required
          />
          <input
            type="date"
            value={form.date}
            onChange={(e) => setForm({ ...form, date: e.target.value })}
            className="rounded-lg px-3 py-2 text-sm outline-none"
            style={{ backgroundColor: '#0f172a', border: '1px solid #334155', color: '#e2e8f0' }}
            required
          />
          <input
            type="text"
            placeholder="Notes (optional)"
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            className="rounded-lg px-3 py-2 text-sm outline-none"
            style={{ backgroundColor: '#0f172a', border: '1px solid #334155', color: '#e2e8f0' }}
          />
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg py-2 text-sm font-medium transition-opacity"
            style={{ backgroundColor: '#10b981', color: '#0f172a', opacity: submitting ? 0.6 : 1 }}
          >
            {submitting ? 'Saving...' : 'Save Income'}
          </button>
        </form>
      )}

      {loading ? (
        <div className="text-sm text-center py-4" style={{ color: '#475569' }}>Loading...</div>
      ) : entries.length === 0 ? (
        <div className="text-sm text-center py-6" style={{ color: '#475569' }}>
          No income yet — add your first one!
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {entries.slice(0, 10).map((e) => (
            <div
              key={e.id}
              className="flex items-center justify-between rounded-lg px-3 py-2.5"
              style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b' }}
            >
              <div>
                <p className="text-sm font-medium" style={{ color: '#e2e8f0' }}>{e.source}</p>
                <p className="text-xs" style={{ color: '#64748b' }}>{fmtDate(e.date)}</p>
              </div>
              <span className="text-sm font-semibold" style={{ color: '#10b981' }}>
                +${fmt(e.amount)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Expense Column ────────────────────────────────────────────────────────────

function ExpenseColumn() {
  const [entries, setEntries] = useState<ExpenseEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [flash, setFlash] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({ amount: '', merchant: '', date: today() })

  const load = async () => {
    try {
      const data = await getExpenses()
      setEntries(data)
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
    const amount = parseFloat(form.amount)
    if (!amount || amount <= 0) { setError('Amount must be greater than 0'); return }
    if (!form.merchant.trim()) { setError('Merchant is required'); return }
    setSubmitting(true)
    try {
      await createExpense({
        amount,
        merchant: form.merchant.trim(),
        date: form.date,
      })
      setForm({ amount: '', merchant: '', date: today() })
      setShowForm(false)
      setFlash(true)
      setTimeout(() => setFlash(false), 2000)
      await load()
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || 'Failed to add expense'
      setError(detail)
    } finally {
      setSubmitting(false)
    }
  }

  const CATEGORY_COLORS: Record<string, string> = {
    Groceries: '#10b981',
    Transportation: '#3b82f6',
    Entertainment: '#f59e0b',
    Utilities: '#8b5cf6',
    Healthcare: '#ec4899',
    Shopping: '#06b6d4',
    Dining: '#f43f5e',
    Other: '#64748b',
  }

  return (
    <div
      className="rounded-xl p-5 flex flex-col gap-4"
      style={{
        backgroundColor: '#1e293b',
        border: flash ? '1px solid #10b981' : '1px solid #334155',
        transition: 'border-color 0.3s',
      }}
    >
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold" style={{ color: '#f43f5e' }}>
          ↓ Expenses
        </h2>
        <button
          onClick={() => { setShowForm(!showForm); setError(null) }}
          className="text-xs px-3 py-1.5 rounded-lg font-medium"
          style={{ backgroundColor: '#2d1515', color: '#f43f5e', border: '1px solid #7f1d1d' }}
        >
          {showForm ? 'Cancel' : '+ Add'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          {error && (
            <p className="text-xs" style={{ color: '#f43f5e' }}>{error}</p>
          )}
          <input
            type="number"
            step="0.01"
            placeholder="Amount"
            value={form.amount}
            onChange={(e) => setForm({ ...form, amount: e.target.value })}
            className="rounded-lg px-3 py-2 text-sm outline-none"
            style={{ backgroundColor: '#0f172a', border: '1px solid #334155', color: '#e2e8f0' }}
            required
          />
          <input
            type="text"
            placeholder="Merchant (e.g. Uber, Whole Foods)"
            value={form.merchant}
            onChange={(e) => setForm({ ...form, merchant: e.target.value })}
            className="rounded-lg px-3 py-2 text-sm outline-none"
            style={{ backgroundColor: '#0f172a', border: '1px solid #334155', color: '#e2e8f0' }}
            required
          />
          <input
            type="date"
            value={form.date}
            onChange={(e) => setForm({ ...form, date: e.target.value })}
            className="rounded-lg px-3 py-2 text-sm outline-none"
            style={{ backgroundColor: '#0f172a', border: '1px solid #334155', color: '#e2e8f0' }}
            required
          />
          <p className="text-xs" style={{ color: '#64748b' }}>
            Category will be AI-assigned after saving
          </p>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg py-2 text-sm font-medium transition-opacity"
            style={{ backgroundColor: '#f43f5e', color: '#fff', opacity: submitting ? 0.6 : 1 }}
          >
            {submitting ? 'Saving...' : 'Save Expense'}
          </button>
        </form>
      )}

      {loading ? (
        <div className="text-sm text-center py-4" style={{ color: '#475569' }}>Loading...</div>
      ) : entries.length === 0 ? (
        <div className="text-sm text-center py-6" style={{ color: '#475569' }}>
          No expenses yet — add your first one!
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {entries.slice(0, 10).map((e) => (
            <div
              key={e.id}
              className="flex items-center justify-between rounded-lg px-3 py-2.5"
              style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b' }}
            >
              <div>
                <p className="text-sm font-medium" style={{ color: '#e2e8f0' }}>{e.merchant}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span
                    className="text-xs px-1.5 py-0.5 rounded"
                    style={{
                      backgroundColor: `${CATEGORY_COLORS[e.category] || '#64748b'}20`,
                      color: CATEGORY_COLORS[e.category] || '#64748b',
                    }}
                  >
                    {e.category}
                  </span>
                  <span className="text-xs" style={{ color: '#64748b' }}>{fmtDate(e.date)}</span>
                </div>
              </div>
              <span className="text-sm font-semibold" style={{ color: '#f43f5e' }}>
                -${fmt(e.amount)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function Transactions() {
  return (
    <div className="grid grid-cols-2 gap-4">
      <IncomeColumn />
      <ExpenseColumn />
    </div>
  )
}
