import { create } from 'zustand'
import type { ModalName } from '../types'

interface UIState {
  activeModal: ModalName | null
  modalProps: Record<string, unknown>
  sidebarOpen: boolean
  openModal: (name: ModalName, props?: Record<string, unknown>) => void
  closeModal: () => void
  toggleSidebar: () => void
  setSidebarOpen: (v: boolean) => void
}

export const useUIStore = create<UIState>((set) => ({
  activeModal: null,
  modalProps: {},
  sidebarOpen: false,
  openModal: (name, props = {}) => set({ activeModal: name, modalProps: props }),
  closeModal: () => set({ activeModal: null, modalProps: {} }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSidebarOpen: (v) => set({ sidebarOpen: v }),
}))
