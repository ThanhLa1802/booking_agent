import { create } from 'zustand'
import { persist } from 'zustand/middleware'

/**
 * UI store — colour scheme preference.
 * Persisted to localStorage so the choice survives reloads.
 */
const useUiStore = create(
  persist(
    (set, get) => ({
      mode: 'light',
      setMode: (mode) => set({ mode }),
      toggleMode: () => set({ mode: get().mode === 'light' ? 'dark' : 'light' }),
    }),
    { name: 'trinity-ui' },
  ),
)

export default useUiStore
