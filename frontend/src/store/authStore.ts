import { create } from 'zustand'
import { setAxiosToken } from '../lib/axios'
import type { User } from '../types'

interface AuthState {
  user: User | null
  accessToken: string | null
  isHydrated: boolean
  login: (tokens: { access: string; refresh: string }, user: User) => void
  logout: () => void
  setAccessToken: (token: string) => void
  setUser: (user: User) => void
  hydrate: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: null,
  isHydrated: false,

  login: ({ access, refresh }, user) => {
    localStorage.setItem('refresh_token', refresh)
    setAxiosToken(access)
    set({ accessToken: access, user, isHydrated: true })
  },

  logout: () => {
    localStorage.removeItem('refresh_token')
    setAxiosToken(null)
    set({ user: null, accessToken: null })
    // Use replace to avoid history pollution
    window.location.replace('/login')
  },

  setAccessToken: (token) => {
    setAxiosToken(token)
    set({ accessToken: token })
  },

  setUser: (user) => set({ user }),

  hydrate: async () => {
    const refresh = localStorage.getItem('refresh_token')
    if (!refresh) { set({ isHydrated: true }); return }
    try {
      const axios = (await import('axios')).default
      const base = (import.meta as any).env.VITE_API_URL ?? 'http://localhost:8000'
      const { data: tokens } = await axios.post(`${base}/api/auth/token/refresh/`, { refresh })
      setAxiosToken(tokens.access)
      set({ accessToken: tokens.access })
      // Use api (not bare axios) so token is attached
      const api = (await import('../lib/axios')).default
      const { data: user } = await api.get<User>('/api/auth/me/')
      set({ user, isHydrated: true })
    } catch {
      localStorage.removeItem('refresh_token')
      setAxiosToken(null)
      set({ isHydrated: true })
    }
  },
}))
