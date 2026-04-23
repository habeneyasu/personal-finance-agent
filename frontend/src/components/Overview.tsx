import { useEffect, useState } from 'react'
import { getIncome, getExpenses } from '../api'
import { IncomeEntry, ExpenseEntry } from '../types'

function fmt(n: number) { return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }) }

function last3Months() {
  const months = []
  for (let i = 2; i >= 0; i--) {
    const d = new Date()
    d.setMonth(d.getMonth() - i)
    months.push({ key: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`, label: d.toLocaleString('default', { month: 'short' }) })
  }
  return months
}

export default function Overview() {
  const [income, setIncome] = useState<IncomeEntry[]>([])
  const [expenses, setExpenses] = useState<ExpenseEntry[]>([])

  async function load() {
    try {
      const [inc, exp] = await Promise.all([getIncome(), getExpenses()])
      setIncome(inc.items || inc || [])
      setExpenses(exp.items || exp || [])
    } catch {}
  }

  useEffect(() => {
    load()
    const id = setInterval(load, 3000)
    return () => clearInterval(id)
  }, [])

  const totalIncome = income.reduce((s, e) => s + Number(e.amount), 0)
  const totalExpenses = expenses.reduce((s, e) => s + Number(e.amount), 0)
  const netSavings = totalIncome - totalExpenses

  const months = last3Months()
  const monthlyData = months.map(m => ({
    label: m.label,
    income: income.filter(e => e.date?.startsWith(m.key)).reduce((s, e) => s + Number(e.amount), 0),
    expenses: expenses.filter(e => e.date?.startsWith(m.key)).reduce((s, e) => s + Number(e.amount), 0),
  }))

  const maxBar = Math.max(...monthlyData.flatMap(m => [m.income, m.expenses]), 1)

  // Pie chart data
  const catMap: Record<string, number> = {}
  expenses.forEach(e => { catMap[e.category || 'Other'] = (catMap[e.category || 'Other'] || 0) + Number(e.amount) })
  const catEntries = Object.entries(catMap).sort((a, b) => b[1] - a[1]).slice(0, 6)
  const PIE_COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#f43f5e', '#8b5cf6', '#06b6d4']

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 24, color: '#f1f5f9' }}>Overview</h1>

      {/* Stat cards */}
      <div className="grid-3col" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 32 }}>
        {[
          { label: 'Total Income', value: fmt(totalIncome), color: '#10b981', bg: '#052e16' },
          { label: 'Total Expenses', value: fmt(totalExpenses), color: '#f43f5e', bg: '#1c0a0a' },
          { label: 'Net Savings', value: fmt(netSavings), color: netSavings >= 0 ? '#10b981' : '#f43f5e', bg: '#1e293b' },
        ].map(card => (
          <div key={card.label} style={{ backgroundColor: '#1e293b', borderRadius: 12, padding: 24, border: `1px solid ${card.color}33` }}>
            <div style={{ fontSize: 13, color: '#64748b', marginBottom: 8 }}>{card.label}</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: card.color }}>{card.value}</div>
          </div>
        ))}
      </div>

      <div className="grid-2col" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        {/* Bar chart */}
        <div style={{ backgroundColor: '#1e293b', borderRadius: 12, padding: 24, border: '1px solid #334155' }}>
          <h3 style={{ margin: '0 0 20px', fontSize: 15, fontWeight: 600, color: '#f1f5f9' }}>Monthly Income vs Expenses</h3>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 20, height: 160 }}>
            {monthlyData.map(m => (
              <div key={m.label} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                <div style={{ width: '100%', display: 'flex', gap: 4, alignItems: 'flex-end', height: 130 }}>
                  <div style={{ flex: 1, backgroundColor: '#10b981', borderRadius: '4px 4px 0 0', height: `${(m.income / maxBar) * 100}%`, minHeight: 2 }} title={`Income: ${fmt(m.income)}`} />
                  <div style={{ flex: 1, backgroundColor: '#f43f5e', borderRadius: '4px 4px 0 0', height: `${(m.expenses / maxBar) * 100}%`, minHeight: 2 }} title={`Expenses: ${fmt(m.expenses)}`} />
                </div>
                <div style={{ fontSize: 12, color: '#64748b' }}>{m.label}</div>
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 16, marginTop: 12 }}>
            <span style={{ fontSize: 12, color: '#10b981', display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 10, height: 10, borderRadius: 2, backgroundColor: '#10b981', display: 'inline-block' }} />Income</span>
            <span style={{ fontSize: 12, color: '#f43f5e', display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 10, height: 10, borderRadius: 2, backgroundColor: '#f43f5e', display: 'inline-block' }} />Expenses</span>
          </div>
        </div>

        {/* Pie chart */}
        <div style={{ backgroundColor: '#1e293b', borderRadius: 12, padding: 24, border: '1px solid #334155' }}>
          <h3 style={{ margin: '0 0 20px', fontSize: 15, fontWeight: 600, color: '#f1f5f9' }}>Expenses by Category</h3>
          {catEntries.length === 0 ? (
            <div style={{ color: '#475569', fontSize: 14, textAlign: 'center', paddingTop: 40 }}>No expense data yet</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {catEntries.map(([cat, amt], i) => (
                <div key={cat} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: PIE_COLORS[i % PIE_COLORS.length], flexShrink: 0 }} />
                  <div style={{ flex: 1, fontSize: 13, color: '#94a3b8' }}>{cat}</div>
                  <div style={{ fontSize: 13, color: '#f1f5f9', fontWeight: 500 }}>{fmt(amt)}</div>
                  <div style={{ width: 80, height: 6, backgroundColor: '#334155', borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{ height: '100%', backgroundColor: PIE_COLORS[i % PIE_COLORS.length], width: `${(amt / totalExpenses) * 100}%`, borderRadius: 3 }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
