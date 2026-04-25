import axios from 'axios'
// Use VITE_API_URL as-is for production, localhost:8000 for local dev
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const api = axios.create({ baseURL: BASE_URL, headers: { 'Content-Type': 'application/json' } })
api.interceptors.request.use(config => {
  const token = localStorage.getItem('pfip_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
export async function login(email: string, password: string) { return (await api.post('/auth/login', { email, password })).data }
export async function register(email: string, password: string) { return (await api.post('/auth/register', { email, password })).data }
// With baseURL …/v1 (stage), resource paths must include /v1/… so the API path is /v1/income, etc.
export async function getIncome() { return (await api.get('/v1/income')).data }
export async function createIncome(payload: { amount: number; source: string; date: string; notes?: string }) { return (await api.post('/v1/income', payload)).data }
export async function getExpenses() { return (await api.get('/v1/expenses')).data }
export async function createExpense(payload: { amount: number; merchant: string; date: string }) { return (await api.post('/v1/expenses', payload)).data }
export async function getGoals() { return (await api.get('/v1/goals')).data }
export async function createGoal(payload: { name: string; target_amount: number; target_date: string }) { return (await api.post('/v1/goals', payload)).data }
export async function queryInsights(question: string) { return (await api.post('/v1/insights/query', { question })).data }
export async function getMetrics() { return (await api.get('/metrics')).data }
