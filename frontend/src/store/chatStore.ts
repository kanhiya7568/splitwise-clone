import { create } from 'zustand'
import type { Message } from '../types'

// WebSocket instances stored OUTSIDE Zustand (non-serializable)
const socketRegistry = new Map<number, WebSocket>()
const retryTimers = new Map<number, ReturnType<typeof setTimeout>>()
const retryCount = new Map<number, number>()

const MAX_RETRIES = 10
const BASE_DELAY = 1000

function getWsUrl(expenseId: number, token: string): string {
  const base = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000'
  return `${base}/ws/chat/${expenseId}/?token=${token}`
}

interface ChatState {
  messages: Record<number, Message[]>
  status: Record<number, 'connecting' | 'open' | 'closed' | 'error' | 'failed'>
  connect: (expenseId: number) => void
  disconnect: (expenseId: number) => void
  sendMessage: (expenseId: number, content: string) => void
  deleteMessage: (expenseId: number, messageId: number) => void
  _onFrame: (expenseId: number, raw: string) => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: {},
  status: {},

  _onFrame: (expenseId, raw) => {
    try {
      const frame = JSON.parse(raw)
      set((s) => {
        const msgs = s.messages[expenseId] ?? []
        switch (frame.type) {
          case 'history':
            return { messages: { ...s.messages, [expenseId]: frame.messages } }
          case 'chat_message':
            return { messages: { ...s.messages, [expenseId]: [...msgs, frame.message] } }
          case 'message_deleted': {
            const updated = msgs.map((m: Message) =>
              m.id === frame.message_id ? { ...m, is_deleted: true, content: '[deleted]' } : m
            )
            return { messages: { ...s.messages, [expenseId]: updated } }
          }
          default:
            return s
        }
      })
    } catch { /* ignore malformed frames */ }
  },

  connect: (expenseId) => {
    if (socketRegistry.has(expenseId)) return
    const { useAuthStore } = require('../store/authStore') as typeof import('./authStore')
    const token = useAuthStore.getState().accessToken
    if (!token) return

    set((s) => ({ status: { ...s.status, [expenseId]: 'connecting' } }))
    const ws = new WebSocket(getWsUrl(expenseId, token))
    socketRegistry.set(expenseId, ws)

    ws.onopen = () => {
      retryCount.set(expenseId, 0)
      set((s) => ({ status: { ...s.status, [expenseId]: 'open' } }))
    }

    ws.onmessage = (e) => get()._onFrame(expenseId, e.data as string)

    ws.onerror = () => set((s) => ({ status: { ...s.status, [expenseId]: 'error' } }))

    ws.onclose = (e) => {
      socketRegistry.delete(expenseId)
      if (e.code === 4001) {
        const { useAuthStore } = require('../store/authStore') as typeof import('./authStore')
        useAuthStore.getState().logout()
        return
      }
      const count = (retryCount.get(expenseId) ?? 0)
      if (count >= MAX_RETRIES) {
        set((s) => ({ status: { ...s.status, [expenseId]: 'failed' } }))
        return
      }
      const delay = Math.min(BASE_DELAY * Math.pow(2, count), 30_000)
      retryCount.set(expenseId, count + 1)
      set((s) => ({ status: { ...s.status, [expenseId]: 'closed' } }))
      const timer = setTimeout(() => get().connect(expenseId), delay)
      retryTimers.set(expenseId, timer)
    }
  },

  disconnect: (expenseId) => {
    const ws = socketRegistry.get(expenseId)
    if (ws) { ws.onclose = null; ws.close(); socketRegistry.delete(expenseId) }
    const timer = retryTimers.get(expenseId)
    if (timer) { clearTimeout(timer); retryTimers.delete(expenseId) }
    retryCount.delete(expenseId)
    set((s) => {
      const { [expenseId]: _, ...msgs } = s.messages
      const { [expenseId]: __, ...status } = s.status
      return { messages: msgs, status }
    })
  },

  sendMessage: (expenseId, content) => {
    const ws = socketRegistry.get(expenseId)
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'chat_message', content }))
    }
  },

  deleteMessage: (expenseId, messageId) => {
    const ws = socketRegistry.get(expenseId)
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'delete_message', message_id: messageId }))
    }
  },
}))
