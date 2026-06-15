import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

const api = axios.create({ baseURL: BASE_URL })

// Attach access token
api.interceptors.request.use((config) => {
  // authStore is imported lazily to avoid circular dependency
  const { useAuthStore } = require('../store/authStore')
  const token = useAuthStore.getState().accessToken
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

let isRefreshing = false
let queue: Array<{ resolve: (v: string) => void; reject: (e: unknown) => void }> = []

function processQueue(error: unknown, token: string | null) {
  queue.forEach((p) => (error ? p.reject(error) : p.resolve(token!)))
  queue = []
}

// 401 → silent refresh → retry
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config
    if (error.response?.status !== 401 || original._retry) {
      return Promise.reject(error)
    }
    const refresh = localStorage.getItem('refresh_token')
    if (!refresh) {
      const { useAuthStore } = await import('../store/authStore')
      useAuthStore.getState().logout()
      return Promise.reject(error)
    }
    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        queue.push({ resolve, reject })
      }).then((token) => {
        original.headers.Authorization = `Bearer ${token}`
        return api(original)
      })
    }
    original._retry = true
    isRefreshing = true
    try {
      const { data } = await axios.post(`${BASE_URL}/api/auth/token/refresh/`, { refresh })
      const { useAuthStore } = await import('../store/authStore')
      useAuthStore.getState().setAccessToken(data.access)
      processQueue(null, data.access)
      original.headers.Authorization = `Bearer ${data.access}`
      return api(original)
    } catch (e) {
      processQueue(e, null)
      const { useAuthStore } = await import('../store/authStore')
      useAuthStore.getState().logout()
      return Promise.reject(e)
    } finally {
      isRefreshing = false
    }
  }
)

export default api
