import { useEffect, useState, useCallback } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts'
import { getIncome, getExpenses } from '../api'
import type { IncomeEntry, ExpenseEntry, MonthlyData, CategoryData } from '../types'

const POLL_INTERVAL = 3000

const PIE_COLORS = [
  '#22c55e', '#3b82f6', '#f59e0b', '#8b5cf6',
  '#ec4899', '#06b6d4', '#ef4444', '#84cc16',
]

// Professional utility functions
function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount)
}

function formatDate(date: string): string {
  return new Date(date).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function getMonthKey(dateStr: string): string {
  const d = new Date(dateStr)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function getMonthLabel(key: string): string {
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

// Professional Stat Card Component
interface StatCardProps {
  label: string
  value: number
  color: string
  prefix?: string
  icon?: React.ReactNode
  trend?: 'up' | 'down' | 'neutral'
}

function StatCard({ label, value, color, prefix = '$', icon, trend }: StatCardProps) {
  const isPositive = value >= 0
  
  return (
    <div className="card hover-lift">
      <div className="card-body">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <p className="text-sm font-medium text-secondary-400 mb-2">{label}</p>
            <div className="flex items-baseline gap-2">
              <span 
                className="text-2xl font-bold"
                style={{ color }}
              >
                {prefix}{formatCurrency(Math.abs(value))}
              </span>
              {trend && (
                <span className={`text-sm font-medium ${
                  trend === 'up' ? 'text-success-400' : 
                  trend === 'down' ? 'text-error-400' : 
                  'text-secondary-400'
                }`}>
                  {trend === 'up' ? 'â' : trend === 'down' ? 'â' : 'â'} 12%
                </span>
              )}
            </div>
            {!isPositive && (
              <p className="text-xs text-error-400 mt-1">Below target</p>
            )}
          </div>
          {icon && (
            <div className="p-2 rounded-lg" style={{ backgroundColor: `${color}20` }}>
              <div style={{ color }}>{icon}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// Professional Loading Component
function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      <div className="loading-spinner w-8 h-8 mb-4"></div>
      <p className="text-secondary-400 text-sm">Loading financial data...</p>
    </div>
  )
}

// Professional Chart Components
const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  
  return (
    <div className="card p-3 shadow-medium">
      <p className="font-medium text-secondary-100 mb-2">{label}</p>
      {payload.map((p: any, index: number) => (
        <div key={index} className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div 
              className="w-2 h-2 rounded-full" 
              style={{ backgroundColor: p.color }}
            />
            <span className="text-sm text-secondary-300">{p.name}</span>
          </div>
          <span className="text-sm font-medium text-secondary-100">
            {formatCurrency(p.value)}
          </span>
        </div>
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
    return <LoadingState />
  }

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header Section */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-100 mb-2">Financial Overview</h1>
          <p className="text-secondary-400">
            Track your income, expenses, and savings at a glance
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm text-secondary-400">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Auto-refreshes every 3s
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="alert alert-error">
          <div className="flex items-center">
            <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            {error}
          </div>
        </div>
      )}

      {/* Stat Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <StatCard
          label="Total Income"
          value={totalIncome}
          color="#22c55e"
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
          }
          trend="up"
        />
        <StatCard
          label="Total Expenses"
          value={totalExpenses}
          color="#ef4444"
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
            </svg>
          }
          trend="down"
        />
        <StatCard
          label="Net Savings"
          value={netSavings}
          color={netSavings >= 0 ? "#22c55e" : "#ef4444"}
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
          }
          trend={netSavings >= 0 ? "up" : "down"}
        />
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Monthly Trend Chart */}
        <div className="card">
          <div className="card-header">
            <h2 className="text-lg font-semibold text-secondary-100">
              Monthly Income vs Expenses
            </h2>
            <p className="text-sm text-secondary-400">
              3-month trend analysis
            </p>
          </div>
          <div className="card-body">
            {monthlyData.every((m) => m.income === 0 && m.expenses === 0) ? (
              <div className="flex flex-col items-center justify-center h-64 text-center">
                <svg className="w-12 h-12 text-secondary-600 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                <p className="text-secondary-400">No data for the last 3 months</p>
                <p className="text-sm text-secondary-500 mt-1">
                  Start adding transactions to see your trends
                </p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={monthlyData} barGap={8} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" strokeOpacity={0.5} />
                  <XAxis 
                    dataKey="month" 
                    tick={{ fill: '#64748b', fontSize: 12 }} 
                    axisLine={false} 
                    tickLine={false} 
                  />
                  <YAxis 
                    tick={{ fill: '#64748b', fontSize: 12 }} 
                    axisLine={false} 
                    tickLine={false} 
                    tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} 
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend 
                    wrapperStyle={{ paddingTop: '20px' }} 
                    iconType="circle"
                  />
                  <Bar 
                    dataKey="income" 
                    name="Income" 
                    fill="#22c55e" 
                    radius={[8, 8, 0, 0]}
                  />
                  <Bar 
                    dataKey="expenses" 
                    name="Expenses" 
                    fill="#ef4444" 
                    radius={[8, 8, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Category Breakdown */}
        <div className="card">
          <div className="card-header">
            <h2 className="text-lg font-semibold text-secondary-100">
              Expenses by Category
            </h2>
            <p className="text-sm text-secondary-400">
              Where your money goes
            </p>
          </div>
          <div className="card-body">
            {categoryData.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-64 text-center">
                <svg className="w-12 h-12 text-secondary-600 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
                <p className="text-secondary-400">No expenses yet</p>
                <p className="text-sm text-secondary-500 mt-1">
                  Add your first expense to see the breakdown
                </p>
              </div>
            ) : (
              <div className="flex items-center gap-6">
                <ResponsiveContainer width="45%" height={280}>
                  <PieChart>
                    <Pie
                      data={categoryData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={2}
                      dataKey="value"
                    >
                      {categoryData.map((_, i) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(v: number) => [formatCurrency(v), '']}
                      contentStyle={{ 
                        backgroundColor: '#1e293b', 
                        border: '1px solid #334155', 
                        borderRadius: '8px'
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex-1 space-y-3">
                  {categoryData.slice(0, 8).map((c, i) => (
                    <div key={c.name} className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div
                          className="w-3 h-3 rounded-full flex-shrink-0"
                          style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }}
                        />
                        <span className="text-sm text-secondary-300 font-medium">
                          {c.name}
                        </span>
                      </div>
                      <span className="text-sm font-semibold text-secondary-100">
                        {formatCurrency(c.value)}
                      </span>
                    </div>
                  ))}
                  {categoryData.length > 8 && (
                    <div className="text-xs text-secondary-500 text-center pt-2">
                      +{categoryData.length - 8} more categories
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Professional Footer */}
      <footer className="mt-12 pt-8 border-t border-secondary-800">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Quick Stats */}
          <div>
            <h3 className="text-sm font-semibold text-secondary-300 mb-4">Quick Stats</h3>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-secondary-400">Avg. Monthly Income</span>
                <span className="text-secondary-200 font-medium">
                  {formatCurrency(totalIncome / 3)}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-secondary-400">Avg. Monthly Expenses</span>
                <span className="text-secondary-200 font-medium">
                  {formatCurrency(totalExpenses / 3)}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-secondary-400">Savings Rate</span>
                <span className={`font-medium ${
                  netSavings >= 0 ? 'text-success-400' : 'text-error-400'
                }`}>
                  {totalIncome > 0 ? 
                    `${((netSavings / totalIncome) * 100).toFixed(1)}%` : 
                    'N/A'
                  }
                </span>
              </div>
            </div>
          </div>

          {/* Recent Activity */}
          <div>
            <h3 className="text-sm font-semibold text-secondary-300 mb-4">Recent Activity</h3>
            <div className="space-y-2">
              {expenses.slice(0, 3).map((expense, index) => (
                <div key={index} className="flex justify-between text-sm">
                  <span className="text-secondary-400 truncate max-w-[150px]">
                    {expense.merchant}
                  </span>
                  <span className="text-error-400 font-medium">
                    -{formatCurrency(Number(expense.amount))}
                  </span>
                </div>
              ))}
              {expenses.length === 0 && (
                <p className="text-secondary-500 text-sm">No recent expenses</p>
              )}
            </div>
          </div>

          {/* Tips & Insights */}
          <div>
            <h3 className="text-sm font-semibold text-secondary-300 mb-4">Financial Tips</h3>
            <div className="space-y-2">
              <p className="text-sm text-secondary-400">
                {netSavings >= 0 
                  ? "Great job! You're saving more than you spend."
                  : "Consider reducing expenses to improve your savings rate."
                }
              </p>
              <p className="text-sm text-secondary-400">
                {categoryData.length > 0 
                  ? `Your top expense category is ${categoryData[0]?.name}.`
                  : "Start tracking expenses to see spending patterns."
                }
              </p>
            </div>
          </div>
        </div>

        {/* Bottom Footer */}
        <div className="mt-8 pt-6 border-t border-secondary-800">
          <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
            <p className="text-xs text-secondary-500">
              © 2026 PFIP. AI-powered financial intelligence platform.
            </p>
            <div className="flex items-center gap-4 text-xs text-secondary-500">
              <span>Last updated: {new Date().toLocaleTimeString()}</span>
              <span>â¢</span>
              <span>Data refreshed automatically</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
