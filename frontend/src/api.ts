import axios from 'axios'

// In production, set VITE_API_URL to your API Gateway URL
// e.g. https://abc123.execute-api.us-east-1.amazonaws.com/v1
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

// Attach JWT token to every request if available
api.interceptors.request.use(config => {
  const token = localStorage.getItem('pfip_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Auth ─────────────────────────────────────────────────────────────────────

export async function login(email: string, password: string) {
  const res = await api.post('/auth/login', { email, password })
  return res.data
}

export async function register(email: string, password: string) {
  const res = await api.post('/auth/register', { email, password })
  return res.data
}

// ── Income ──────────────────────────────────────────────────────────────────

export async function getIncome() {
  const res = await api.get('/v1/income')
  return res.data
}

export async function createIncome(payload: {
  amount: number
  source: string
  date: string
  notes?: string
}) {
  const res = await api.post('/v1/income', payload)
  return res.data
}

// ── Expenses ─────────────────────────────────────────────────────────────────

export async function getExpenses() {
  const res = await api.get('/v1/expenses')
  return res.data
}

export async function createExpense(payload: {
  amount: number
  merchant: string
  date: string
}) {
  const res = await api.post('/v1/expenses', payload)
  return res.data
}

// ── Goals ────────────────────────────────────────────────────────────────────

export async function getGoals() {
  const res = await api.get('/v1/goals')
  return res.data
}

export async function createGoal(payload: {
  name: string
  target_amount: number
  target_date: string
}) {
  const res = await api.post('/v1/goals', payload)
  return res.data
}

// ── Insights ─────────────────────────────────────────────────────────────────

export async function queryInsights(question: string) {
  const res = await api.post('/v1/insights/query', { question })
  return res.data
}
