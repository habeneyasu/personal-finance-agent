export interface IncomeEntry { id: string; user_id: string; amount: number; source: string; date: string; notes?: string; created_at: string }
export interface ExpenseEntry { id: string; user_id: string; amount: number; merchant: string; category: string; date: string; created_at: string }
export interface SavingsGoal { id: string; user_id: string; name: string; target_amount: number; current_amount: number; initial_amount?: number; target_date: string; created_at: string; progress_pct?: number; predicted_completion_date?: string }
export interface InsightMessage { role: 'user' | 'assistant'; content: string; timestamp: string; decision?: string; reason?: string; retried?: boolean; data_sources?: string[] }
export interface MetricItem { id: string; label: string; description: string; value: number; baseline: number; unit: string; status: 'green' | 'yellow' | 'red'; detail: string }

export interface LlmUsage {
  total_calls: number
  total_tokens: number
  total_cost_usd: number
  avg_latency_ms: number
  max_latency_ms: number
}

export interface LlmAgentUsage {
  agent: string
  calls: number
  tokens: number
  cost_usd: number
  avg_latency_ms: number
}

export interface MetricsResponse {
  computed_at: string
  metrics: MetricItem[]
  llm_usage?: LlmUsage
  llm_usage_by_agent?: LlmAgentUsage[]
  summary: {
    total_income_entries: number
    total_expense_entries: number
    total_goals: number
    passing_metrics: number
  }
}
