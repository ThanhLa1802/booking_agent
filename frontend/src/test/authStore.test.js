import { describe, it, expect, beforeEach } from 'vitest'
import { act } from 'react'
import useAuthStore from '../stores/authStore'

describe('authStore', () => {
    beforeEach(() => {
        useAuthStore.setState({
            accessToken: null,
            refreshToken: null,
            user: null,
        })
    })

    it('sets tokens', () => {
        act(() => {
            useAuthStore.getState().setTokens('access123', 'refresh456')
        })
        const state = useAuthStore.getState()
        expect(state.accessToken).toBe('access123')
        expect(state.refreshToken).toBe('refresh456')
    })

    it('isAuthenticated returns true with access token', () => {
        act(() => {
            useAuthStore.getState().setTokens('access123', 'refresh456')
        })
        expect(useAuthStore.getState().isAuthenticated()).toBe(true)
    })

    it('isAuthenticated returns false without access token', () => {
        expect(useAuthStore.getState().isAuthenticated()).toBe(false)
    })

    it('logout clears all tokens and user', () => {
        act(() => {
            useAuthStore.getState().setTokens('a', 'r')
            useAuthStore.getState().setUser({ id: 1, email: 'test@example.com' })
            useAuthStore.getState().logout()
        })
        const state = useAuthStore.getState()
        expect(state.accessToken).toBeNull()
        expect(state.refreshToken).toBeNull()
        expect(state.user).toBeNull()
    })

    it('setAccessToken only updates accessToken', () => {
        act(() => {
            useAuthStore.getState().setTokens('old', 'refresh')
            useAuthStore.getState().setAccessToken('new')
        })
        const state = useAuthStore.getState()
        expect(state.accessToken).toBe('new')
        expect(state.refreshToken).toBe('refresh')
    })
})
