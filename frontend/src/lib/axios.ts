import axios, { type AxiosInstance } from 'axios'

const BASE_URL = (import.meta as any).env.VITE_API_URL ?? 'http://localhost:8000'

// Token stored in closure — avoids circular import with authStore
let _accessToken: string | null = null
export function setAxiosToken(token: string | null) { _accessToken = token }

const api: AxiosInstance = axios.create({ baseURL: BASE_URL })

// Attach access token to every request
api.interceptors.request.use((config) => {
  if (_accessToken) config.headers.Authorization = `Bearer ${_accessToken}`
  return config
})

// 401 → silent refresh → retry original request
let _isRefreshing = false
type QueueEntry = { resolve: (v: string) => void; reject: (e: unknown) => void }
let _queue: QueueEntry[] = []

function processQueue(err: unknown, token: string | null) {
  _queue.forEach(p => err ? p.reject(err) : p.resolve(token!))
  _queue = []
}

api.interceptors.response.use(
  r => r,
  async (error) => {
    const original = error.config as typeof error.config & { _retry?: boolean }
    if (error.response?.status !== 401 || original._retry) return Promise.reject(error)

    const refresh = localStorage.getItem('refresh_token')
    if (!refresh) {
      // Lazy import to avoid circular dependency at module load time
      const { useAuthStore } = await import('../store/authStore')
      useAuthStore.getState().logout()
      return Promise.reject(error)
    }

    if (_isRefreshing) {
      return new Promise<string>((resolve, reject) => _queue.push({ resolve, reject }))
        .then(token => {
          original.headers.Authorization = `Bearer ${token}`
          return api(original)
        })
    }

    original._retry = true
    _isRefreshing = true

    try {
      const { data } = await axios.post(`${BASE_URL}/api/auth/token/refresh/`, { refresh })
      setAxiosToken(data.access)
      processQueue(null, data.access)
      // Update authStore without circular import
      const { useAuthStore } = await import('../store/authStore')
      useAuthStore.getState().setAccessToken(data.access)
      original.headers.Authorization = `Bearer ${data.access}`
      return api(original)
    } catch (e) {
      processQueue(e, null)
      localStorage.removeItem('refresh_token')
      const { useAuthStore } = await import('../store/authStore')
      useAuthStore.getState().logout()
      return Promise.reject(e)
    } finally {
      _isRefreshing = false
    }
  }
)

export default api
