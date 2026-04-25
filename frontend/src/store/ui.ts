import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface UIState {
  sidebarCollapsed: boolean
  toggleSidebar: () => void
  setSidebarCollapsed: (v: boolean) => void
  /** Sistema de unidades preferido (exibição). Backend sempre em SI. */
  unitSystem: 'metric' | 'imperial'
  setUnitSystem: (u: 'metric' | 'imperial') => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      toggleSidebar: () =>
        set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
      unitSystem: 'metric',
      setUnitSystem: (u) => set({ unitSystem: u }),
    }),
    { name: 'ancoplat-ui' },
  ),
)
