import { useEffect, useState, useCallback } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts'
import { getIncome, getExpenses } from '../api'
import type { IncomeEntry, ExpenseEntry, MonthlyData, CategoryData } from '../types'

const POLL_INTERVAL = 3000

const PIE_COLORS = [
  '#10b981', '#3b82f6', '#f59e0b', '#8b5cf6',
  '#ec4899', '#06b6d4', '#f43f5e', '#84cc16',
]

function fmt(n: number) {
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtDate(d: string) {
  return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function getMonthKey(dateStr: string) {
  const d = new Date(dateStr)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function getMonthLabel(key: string) {
  const [year, month] = key.split('-')
  return new Date(Number(year), Number(month) - 1, 1).toLocaleDateString('en-US', {
    month: 'short',
    year: '2-digit',
  })
}

function buildMonthlyData(income: IncomeEntry[], expenses: ExpenseEntry[]): MonthlyData[] {
  const now = new Date()
  const months: string[] = []
  for (let i = 2; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    months.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`)
  }

  const incomeByMonth: Record<string, number> = {}
  const expenseByMonth: Record<string, number> = {}

  income.forEach((e) => {
    const k = getMonthKey(e.date)
    incomeByMonth[k] = (incomeByMonth[k] || 0) + Number(e.amount)
  })
  expenses.forEach((e) => {
    const k = getMonthKey(e.date)
    expenseByMonth[k] = (expenseByMonth[k] || 0) + Number(e.amount)
  })

  return months.map((m) => ({
    month: getMonthLabel(m),
    income: Math.round((incomeByMonth[m] || 0) * 100) / 100,
    expenses: Math.round((expenseByMonth[m] || 0) * 100) / 100,
  }))
}

function buildCategoryData(expenses: ExpenseEntry[]): CategoryData[] {
  const byCategory: Record<string, number> = {}
  expenses.forEach((e) => {
    byCategory[e.category] = (byCategory[e.category] || 0) + Number(e.amount)
  })
  return Object.entries(byCategory)
    .map(([name, value]) => ({ name, value: Math.round(value * 100) / 100 }))
    .sort((a, b) => b.value - a.value)
}

interface StatCardProps {
  label: string
  value: number
  color: string
  prefix?: string
}

function StatCard({ label, value, color, prefix = '$' }: StatCardProps) {
  return (
    <div
      className="rounded-xl p-5 flex flex-col gap-1"
      style={{ backgroundColor: '#1e293b', border: '1px solid #334155' }}
    >
      <span className="text-xs font-medium uppercase tracking-wider" style={{ color: '#64748b' }}>
        {label}
      </span>
      <span className="text-2xl font-semibold" style={{ color }}>
        {prefix}{fmt(Math.abs(value))}
        {value < 0 && <span className="text-base ml-1" style={{ color: '#f43f5e' }}>▼</span>}
      </span>
    </div>
  )
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div
      className="rounded-lg p-3 text-sm"
      style={{ backgroundColor: '#1e293b', border: '1px solid #334155', color: '#e2e8f0' }}
    >
      <p className="font-medium mb-1">{label}</p>
      {payload.map((p: any) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: ${fmt(p.value)}
        </p>
      ))}
    </div>
  )
}

export default function Overview() {
  const [income, setIncome] = useState<IncomeEntry[]>([])
  const [expenses, setExpenses] = useState<ExpenseEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    try {
      const [inc, exp] = await Promise.all([getIncome(), getExpenses()])
      setIncome(inc)
      setExpenses(exp)
      setError(null)
    } catch (e: any) {
      setError(e?.message || 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const id = setInterval(fetchData, POLL_INTERVAL)
    return () => clearInterval(id)
  }, [fetchData])

  const totalIncome = income.reduce((s, e) => s + Number(e.amount), 0)
  const totalExpenses = expenses.reduce((s, e) => s + Number(e.amount), 0)
  const netSavings = totalIncome - totalExpenses

  const monthlyData = buildMonthlyData(income, expenses)
  const categoryData = buildCategoryData(expenses)

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-3" style={{ color: '#64748b' }}>
          <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
          </svg>
          Loading financial data...
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      {error && (
        <div
          className="rounded-lg px-4 py-3 text-sm"
          style={{ backgroundColor: '#2d1515', border: '1px solid #7f1d1d', color: '#fca5a5' }}
        >
          {error}
        </div>
      )}

      {/* Stat Cards */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Total Income" value={totalIncome} color="#10b981" />
        <StatCard label="Total Expenses" value={totalExpenses} color="#f43f5e" />
        <StatCard
          label="Net Savings"
          value={netSavings}
          color={netSavings >= 0 ? '#10b981' : '#f43f5e'}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-2 gap-4">
        {/* Bar Chart */}
        <div
          className="rounded-xl p-5"
          style={{ backgroundColor: '#1e293b', border: '1px solid #334155' }}
        >
          <h2 className="text-sm font-semibold mb-4" style={{ color: '#94a3b8' }}>
            Monthly Income vs Expenses
          </h2>
          {monthlyData.every((m) => m.income === 0 && m.expenses === 0) ? (
            <div className="flex items-center justify-center h-48 text-sm" style={{ color: '#475569' }}>
              No data for the last 3 months
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={monthlyData} barGap={4}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="month" tick={{ fill: '#64748b', fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#64748b', fontSize: 12 }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v}`} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ color: '#94a3b8', fontSize: 12 }} />
                <Bar dataKey="income" name="Income" fill="#10b981" radius={[4, 4, 0, 0]} />
                <Bar dataKey="expenses" name="Expenses" fill="#f43f5e" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Pie Chart */}
        <div
          className="rounded-xl p-5"
          style={{ backgroundColor: '#1e293b', border: '1px solid #334155' }}
        >
          <h2 className="text-sm font-semibold mb-4" style={{ color: '#94a3b8' }}>
            Expenses by Category
          </h2>
          {categoryData.length === 0 ? (
            <div className="flex items-center justify-center h-48 text-sm" style={{ color: '#475569' }}>
              No expenses yet — add your first one!
            </div>
          ) : (
            <div className="flex items-center gap-4">
              <ResponsiveContainer width="55%" height={220}>
                <PieChart>
                  <Pie
                    data={categoryData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={90}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {categoryData.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(v: number) => [`$${fmt(v)}`, '']}
                    contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', color: '#e2e8f0' }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex flex-col gap-2 flex-1">
                {categoryData.slice(0, 6).map((c, i) => (
                  <div key={c.name} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-2 h-2 rounded-full flex-shrink-0"
                        style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }}
                      />
                      <span style={{ color: '#94a3b8' }}>{c.name}</span>
                    </div>
                    <span style={{ color: '#e2e8f0' }}>${fmt(c.value)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <p className="text-xs text-right" style={{ color: '#334155' }}>
        Auto-refreshes every 3s
      </p>
    </div>
  )
}
