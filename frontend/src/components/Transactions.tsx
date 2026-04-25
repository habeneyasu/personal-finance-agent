import { useEffect, useState } from 'react'
import { getIncome, createIncome, getExpenses, createExpense } from '../api'
import { IncomeEntry, ExpenseEntry } from '../types'

function fmt(n: number) { return n.toLocaleString('en-US', { style: 'currency', currency: 'USD' }) }
function today() { return new Date().toISOString().split('T')[0] }

const CAT_COLORS: Record<string, string> = {
  Food: '#f59e0b', Transport: '#3b82f6', Entertainment: '#8b5cf6',
  Healthcare: '#10b981', Shopping: '#f43f5e', Utilities: '#06b6d4', Other: '#64748b',
}

export default function Transactions() {
  const [income, setIncome] = useState<IncomeEntry[]>([])
  const [expenses, setExpenses] = useState<ExpenseEntry[]>([])
  const [showIncomeForm, setShowIncomeForm] = useState(false)
  const [showExpenseForm, setShowExpenseForm] = useState(false)
  const [incomeForm, setIncomeForm] = useState({ amount: '', source: '', date: today(), notes: '' })
  const [expenseForm, setExpenseForm] = useState({ amount: '', merchant: '', date: today() })
  const [saving, setSaving] = useState(false)

  async function load() {
    try {
      const [inc, exp] = await Promise.all([getIncome(), getExpenses()])
      setIncome(inc.items || inc || [])
      setExpenses(exp.items || exp || [])
    } catch {}
  }

  useEffect(() => { load() }, [])

  async function submitIncome(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    try {
      await createIncome({ amount: parseFloat(incomeForm.amount), source: incomeForm.source, date: incomeForm.date, notes: incomeForm.notes || undefined })
      setIncomeForm({ amount: '', source: '', date: today(), notes: '' })
      setShowIncomeForm(false)
      load()
    } catch {} finally { setSaving(false) }
  }

  async function submitExpense(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    try {
      await createExpense({ amount: parseFloat(expenseForm.amount), merchant: expenseForm.merchant, date: expenseForm.date })
      setExpenseForm({ amount: '', merchant: '', date: today() })
      setShowExpenseForm(false)
      load()
    } catch {} finally { setSaving(false) }
  }

  const inputStyle = { width: '100%', padding: '8px 12px', borderRadius: 6, border: '1px solid #334155', backgroundColor: '#0f172a', color: '#f1f5f9', fontSize: 13, outline: 'none', boxSizing: 'border-box' as const }

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 24, color: '#f1f5f9' }}>Transactions</h1>
      <div className="grid-2col" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>

        {/* Income */}
        <div style={{ backgroundColor: '#1e293b', borderRadius: 12, padding: 24, border: '1px solid #334155' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: '#10b981' }}>Income</h2>
            <button onClick={() => setShowIncomeForm(!showIncomeForm)} style={{ padding: '6px 14px', borderRadius: 6, border: 'none', backgroundColor: '#10b981', color: '#fff', fontSize: 13, cursor: 'pointer', fontWeight: 500 }}>
              + Add
            </button>
          </div>

          {showIncomeForm && (
            <form onSubmit={submitIncome} style={{ marginBottom: 16, padding: 16, backgroundColor: '#0f172a', borderRadius: 8, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <input style={inputStyle} placeholder="Amount" type="number" step="0.01" value={incomeForm.amount} onChange={e => setIncomeForm(f => ({ ...f, amount: e.target.value }))} required />
              <input style={inputStyle} placeholder="Source (e.g. Salary)" value={incomeForm.source} onChange={e => setIncomeForm(f => ({ ...f, source: e.target.value }))} required />
              <input style={inputStyle} type="date" value={incomeForm.date} onChange={e => setIncomeForm(f => ({ ...f, date: e.target.value }))} required />
              <input style={inputStyle} placeholder="Notes (optional)" value={incomeForm.notes} onChange={e => setIncomeForm(f => ({ ...f, notes: e.target.value }))} />
              <button type="submit" disabled={saving} style={{ padding: '8px', borderRadius: 6, border: 'none', backgroundColor: '#10b981', color: '#fff', fontSize: 13, cursor: 'pointer', fontWeight: 500 }}>
                {saving ? 'Saving...' : 'Save'}
              </button>
            </form>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {income.slice(0, 10).map(e => (
              <div key={e.id} style={{ padding: '10px 14px', backgroundColor: '#0f172a', borderRadius: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500, color: '#f1f5f9' }}>{e.source}</div>
                  <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>{e.date}</div>
                </div>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#10b981' }}>+{fmt(e.amount)}</div>
              </div>
            ))}
            {income.length === 0 && <div style={{ color: '#475569', fontSize: 13, textAlign: 'center', padding: 20 }}>No income entries yet</div>}
          </div>
        </div>

        {/* Expenses */}
        <div style={{ backgroundColor: '#1e293b', borderRadius: 12, padding: 24, border: '1px solid #334155' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: '#f43f5e' }}>Expenses</h2>
            <button onClick={() => setShowExpenseForm(!showExpenseForm)} style={{ padding: '6px 14px', borderRadius: 6, border: 'none', backgroundColor: '#f43f5e', color: '#fff', fontSize: 13, cursor: 'pointer', fontWeight: 500 }}>
              + Add
            </button>
          </div>

          {showExpenseForm && (
            <form onSubmit={submitExpense} style={{ marginBottom: 16, padding: 16, backgroundColor: '#0f172a', borderRadius: 8, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <input style={inputStyle} placeholder="Amount" type="number" step="0.01" value={expenseForm.amount} onChange={e => setExpenseForm(f => ({ ...f, amount: e.target.value }))} required />
              <input style={inputStyle} placeholder="Merchant (e.g. Starbucks)" value={expenseForm.merchant} onChange={e => setExpenseForm(f => ({ ...f, merchant: e.target.value }))} required />
              <input style={inputStyle} type="date" value={expenseForm.date} onChange={e => setExpenseForm(f => ({ ...f, date: e.target.value }))} required />
              <button type="submit" disabled={saving} style={{ padding: '8px', borderRadius: 6, border: 'none', backgroundColor: '#f43f5e', color: '#fff', fontSize: 13, cursor: 'pointer', fontWeight: 500 }}>
                {saving ? 'Saving...' : 'Save'}
              </button>
            </form>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {expenses.slice(0, 10).map(e => (
              <div key={e.id} style={{ padding: '10px 14px', backgroundColor: '#0f172a', borderRadius: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500, color: '#f1f5f9' }}>{e.merchant}</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
                    <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 4, backgroundColor: `${CAT_COLORS[e.category] || '#64748b'}22`, color: CAT_COLORS[e.category] || '#64748b', fontWeight: 500 }}>{e.category || 'Other'}</span>
                    <span style={{ fontSize: 11, color: '#475569' }}>{e.date}</span>
                  </div>
                </div>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#f43f5e' }}>-{fmt(e.amount)}</div>
              </div>
            ))}
            {expenses.length === 0 && <div style={{ color: '#475569', fontSize: 13, textAlign: 'center', padding: 20 }}>No expense entries yet</div>}
          </div>
        </div>
      </div>
    </div>
  )
}
