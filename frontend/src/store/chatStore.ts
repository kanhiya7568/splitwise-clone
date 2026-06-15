import { create } from 'zustand'
import { useAuthStore } from './authStore'
import type { Message } from '../types'

const WS_BASE = (import.meta as any).env.VITE_WS_URL ?? 'ws://localhost:8000'
const MAX_RETRIES = 10
const BASE_DELAY_MS = 1000

// WebSocket instances live OUTSIDE Zustand — non-serializable
const socketRegistry = new Map<number, WebSocket>()
const retryTimers = new Map<number, ReturnType<typeof setTimeout>>()
const retryCount = new Map<number, number>()

function buildWsUrl(expenseId: number, token: string) {
  return `${WS_BASE}/ws/chat/${expenseId}/?token=${token}`
}

interface ChatState {
  messages: Record<number, Message[]>
  status: Record<number, 'connecting' | 'open' | 'closed' | 'error' | 'failed'>
  connect: (expenseId: number) => void
  disconnect: (expenseId: number) => void
  sendMessage: (expenseId: number, content: string) => void
  deleteMessage: (expenseId: number, messageId: number) => void
  _processFrame: (expenseId: number, raw: string) => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: {},
  status: {},

  _processFrame: (expenseId, raw) => {
    try {
      const frame = JSON.parse(raw) as {
        type: string
        messages?: Message[]
        message?: Message
        message_id?: number
      }
      set(s => {
        const prev = s.messages[expenseId] ?? []
        switch (frame.type) {
          case 'history':
            return { messages: { ...s.messages, [expenseId]: frame.messages ?? [] } }
          case 'chat_message':
            return frame.message
              ? { messages: { ...s.messages, [expenseId]: [...prev, frame.message] } }
              : s
          case 'message_deleted': {
            const updated = prev.map(m =>
              m.id === frame.message_id ? { ...m, is_deleted: true, content: '[deleted]' } : m
            )
            return { messages: { ...s.messages, [expenseId]: updated } }
          }
          default:
            return s
        }
      })
    } catch {
      // Swallow malformed frames silently
    }
  },

  connect: (expenseId) => {
    if (socketRegistry.has(expenseId)) return

    // Always read the CURRENT token at connect time (handles reconnect after expiry)
    const token = useAuthStore.getState().accessToken
    if (!token) return

    set(s => ({ status: { ...s.status, [expenseId]: 'connecting' } }))

    const ws = new WebSocket(buildWsUrl(expenseId, token))
    socketRegistry.set(expenseId, ws)

    ws.onopen = () => {
      retryCount.set(expenseId, 0)
      set(s => ({ status: { ...s.status, [expenseId]: 'open' } }))
    }

    ws.onmessage = e => get()._processFrame(expenseId, e.data as string)

    ws.onerror = () => {
      set(s => ({ status: { ...s.status, [expenseId]: 'error' } }))
    }

    ws.onclose = e => {
      socketRegistry.delete(expenseId)

      // 4001 = invalid auth → logout
      if (e.code === 4001) {
        useAuthStore.getState().logout()
        return
      }
      // 4003 = forbidden, 4004 = not found → don't retry
      if (e.code === 4003 || e.code === 4004) {
        set(s => ({ status: { ...s.status, [expenseId]: 'failed' } }))
        return
      }

      const count = retryCount.get(expenseId) ?? 0
      if (count >= MAX_RETRIES) {
        set(s => ({ status: { ...s.status, [expenseId]: 'failed' } }))
        return
      }

      const delay = Math.min(BASE_DELAY_MS * Math.pow(2, count), 30_000)
      retryCount.set(expenseId, count + 1)
      set(s => ({ status: { ...s.status, [expenseId]: 'closed' } }))

      const timer = setTimeout(() => get().connect(expenseId), delay)
      retryTimers.set(expenseId, timer)
    }
  },

  disconnect: (expenseId) => {
    const ws = socketRegistry.get(expenseId)
    if (ws) {
      ws.onclose = null  // prevent reconnect on intentional close
      ws.close()
      socketRegistry.delete(expenseId)
    }
    const timer = retryTimers.get(expenseId)
    if (timer) { clearTimeout(timer); retryTimers.delete(expenseId) }
    retryCount.delete(expenseId)
    set(s => {
      const { [expenseId]: _m, ...msgs } = s.messages
      const { [expenseId]: _st, ...status } = s.status
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
