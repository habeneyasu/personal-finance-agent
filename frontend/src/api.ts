import axios from 'axios'

const rawBase = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')
const isAwsExecuteApi =
  rawBase.includes('execute-api.') && rawBase.includes('.amazonaws.com')

// For AWS: base is https://<id>.execute-api.<region>.amazonaws.com/api
// Auth routes live at /api/auth/*, data routes at /api/v1/*
const awsBase = (() => {
  if (!isAwsExecuteApi) return rawBase
  // Strip any trailing /v1 or /api/v1 to get the stage root
  return rawBase.replace(/\/api\/v1$/, '/api').replace(/\/v1$/, '/api')
})()

const api = axios.create({
  baseURL: isAwsExecuteApi ? awsBase : rawBase,
  headers: { 'Content-Type': 'application/json' },
})

/** Returns the correct path for each endpoint. */
function apiPath(path: string): string {
  if (!isAwsExecuteApi) return path.startsWith('/') ? path : `/${path}`
  // Auth routes: /auth/* → no /v1 prefix
  if (path.startsWith('/auth') || path.startsWith('auth')) {
    return path.startsWith('/') ? path : `/${path}`
  }
  // Data routes: /income, /expenses, etc. → /v1/*
  const clean = path.startsWith('/') ? path : `/${path}`
  return `/v1${clean}`
}

api.interceptors.request.use(config => {
  const token = localStorage.getItem('pfip_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('pfip_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
export async function login(email: string, password: string) {
  return (await api.post(apiPath('/auth/login'), { email, password })).data
}
export async function register(email: string, password: string) {
  return (await api.post(apiPath('/auth/register'), { email, password })).data
}
export async function getIncome() { return (await api.get(apiPath('/income'))).data }
export async function createIncome(payload: { amount: number; source: string; date: string; notes?: string }) {
  return (await api.post(apiPath('/income'), payload)).data
}
export async function getExpenses() { return (await api.get(apiPath('/expenses'))).data }
export async function createExpense(payload: { amount: number; merchant: string; date: string }) {
  return (await api.post(apiPath('/expenses'), payload)).data
}
export async function getGoals() { return (await api.get(apiPath('/goals'))).data }
export async function createGoal(payload: { name: string; target_amount: number; target_date: string }) {
  return (await api.post(apiPath('/goals'), payload)).data
}
export async function queryInsights(question: string) {
  return (await api.post(apiPath('/insights/query'), { question })).data
}
export async function getMetrics() { return (await api.get(apiPath('/metrics'))).data }
