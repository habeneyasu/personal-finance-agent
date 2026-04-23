import { useEffect, useState } from 'react'
import { getGoals, createGoal } from '../api'
import { SavingsGoal } from '../types'

function fmt(n: number) { return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }) }
function today() { return new Date().toISOString().split('T')[0] }

export default function Goals() {
  const [goals, setGoals] = useState<SavingsGoal[]>([])
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', target_amount: '', target_date: today() })
  const [saving, setSaving] = useState(false)

  async function load() {
    try {
      const data = await getGoals()
      setGoals(data.items || data || [])
    } catch {}
  }

  useEffect(() => { load() }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    try {
      await createGoal({ name: form.name, target_amount: parseFloat(form.target_amount), target_date: form.target_date })
      setForm({ name: '', target_amount: '', target_date: today() })
      setShowForm(false)
      load()
    } catch {} finally { setSaving(false) }
  }

  const inputStyle = { width: '100%', padding: '8px 12px', borderRadius: 6, border: '1px solid #334155', backgroundColor: '#0f172a', color: '#f1f5f9', fontSize: 13, outline: 'none', boxSizing: 'border-box' as const }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0, color: '#f1f5f9' }}>Savings Goals</h1>
        <button onClick={() => setShowForm(!showForm)} style={{ padding: '10px 20px', borderRadius: 8, border: 'none', backgroundColor: '#10b981', color: '#fff', fontSize: 14, cursor: 'pointer', fontWeight: 600 }}>
          + New Goal
        </button>
      </div>

      {showForm && (
        <div style={{ backgroundColor: '#1e293b', borderRadius: 12, padding: 24, border: '1px solid #334155', marginBottom: 24 }}>
          <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 600, color: '#f1f5f9' }}>Add Goal</h3>
          <form onSubmit={handleSubmit} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr auto', gap: 12, alignItems: 'end' }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: '#64748b', marginBottom: 4 }}>Goal Name</label>
              <input style={inputStyle} placeholder="e.g. Emergency Fund" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} required />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: '#64748b', marginBottom: 4 }}>Target Amount</label>
              <input style={inputStyle} type="number" step="0.01" placeholder="10000" value={form.target_amount} onChange={e => setForm(f => ({ ...f, target_amount: e.target.value }))} required />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: '#64748b', marginBottom: 4 }}>Target Date</label>
              <input style={inputStyle} type="date" value={form.target_date} onChange={e => setForm(f => ({ ...f, target_date: e.target.value }))} required />
            </div>
            <button type="submit" disabled={saving} style={{ padding: '8px 20px', borderRadius: 6, border: 'none', backgroundColor: '#10b981', color: '#fff', fontSize: 13, cursor: 'pointer', fontWeight: 500, height: 36 }}>
              {saving ? '...' : 'Save'}
            </button>
          </form>
        </div>
      )}

      {goals.length === 0 ? (
        <div style={{ backgroundColor: '#1e293b', borderRadius: 12, padding: 48, border: '1px solid #334155', textAlign: 'center', color: '#475569' }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>🎯</div>
          <div style={{ fontSize: 15 }}>No savings goals yet. Create your first goal!</div>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 }}>
          {goals.map(goal => {
            const pct = goal.progress_pct ?? (goal.target_amount > 0 ? Math.min((goal.current_amount / goal.target_amount) * 100, 100) : 0)
            return (
              <div key={goal.id} style={{ backgroundColor: '#1e293b', borderRadius: 12, padding: 24, border: '1px solid #334155' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
                  <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: '#f1f5f9' }}>{goal.name}</h3>
                  <span style={{ fontSize: 13, fontWeight: 700, color: '#10b981' }}>{pct.toFixed(0)}%</span>
                </div>

                <div style={{ marginBottom: 12 }}>
                  <div style={{ height: 8, backgroundColor: '#334155', borderRadius: 4, overflow: 'hidden' }}>
                    <div style={{ height: '100%', backgroundColor: '#10b981', width: `${pct}%`, borderRadius: 4, transition: 'width 0.3s' }} />
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, color: '#94a3b8', marginBottom: 12 }}>
                  <span>{fmt(goal.current_amount)} saved</span>
                  <span>of {fmt(goal.target_amount)}</span>
                </div>

                <div style={{ fontSize: 12, color: '#64748b', display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <div>Target: {goal.target_date}</div>
                  {goal.predicted_completion_date && (
                    <div style={{ color: '#10b981' }}>Predicted: {goal.predicted_completion_date}</div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
