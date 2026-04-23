export interface IncomeEntry {
  id: string
  user_id: string
  amount: number
  source: string
  date: string
  notes?: string | null
  created_at: string
}

export interface ExpenseEntry {
  id: string
  user_id: string
  amount: number
  merchant: string
  category: string
  date: string
  created_at: string
}

export interface SavingsGoal {
  id: string
  user_id: string
  name: string
  target_amount: number
  current_amount: number
  target_date: string
  created_at: string
  progress_pct?: number
  predicted_completion_date?: string | null
}

export interface InsightMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

export interface MonthlyData {
  month: string
  income: number
  expenses: number
}

export interface CategoryData {
  name: string
  value: number
}
