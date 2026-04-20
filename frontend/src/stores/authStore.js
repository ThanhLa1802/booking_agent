import { create } from 'zustand'
import { persist } from 'zustand/middleware'

/**
 * Auth store — accessToken kept in memory only (no XSS risk).
 * refreshToken persisted to localStorage via zustand/persist.
 */
const useAuthStore = create(
    persist(
        (set, get) => ({
            accessToken: null,       // in-memory only
            refreshToken: null,      // persisted
            user: null,              // { id, email, role }
            isHydrating: true,       // true until first token refresh attempt completes

            setTokens: (accessToken, refreshToken) =>
                set({ accessToken, refreshToken }),

            setUser: (user) => set({ user }),

            setAccessToken: (accessToken) => set({ accessToken }),

            setHydrated: () => set({ isHydrating: false }),

            logout: () => set({ accessToken: null, refreshToken: null, user: null }),

            isAuthenticated: () => Boolean(get().accessToken),
        }),
        {
            name: 'trinity-auth',
            // Only persist refreshToken + user; accessToken stays in memory
            partialize: (state) => ({
                refreshToken: state.refreshToken,
                user: state.user,
            }),
        }
    )
)

export default useAuthStore
