// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import LoginPage from '../pages/LoginPage'
import * as api from '../api'

// Minimal MUI theme wrapper not needed — MUI works without ThemeProvider in tests

vi.mock('../api', () => ({
    login: vi.fn(),
    refreshAccessToken: vi.fn(),
}))

vi.mock('../stores/authStore', () => ({
    default: () => ({
        setTokens: vi.fn(),
        setUser: vi.fn(),
        accessToken: null,
        refreshToken: null,
        logout: vi.fn(),
        isAuthenticated: () => false,
        user: null,
    }),
}))

const renderLogin = () =>
    render(
        <MemoryRouter>
            <LoginPage />
        </MemoryRouter>
    )

describe('LoginPage', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('renders email and password fields', () => {
        renderLogin()
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
        expect(screen.getByLabelText(/mật khẩu/i)).toBeInTheDocument()
    })

    it('shows error on failed login', async () => {
        api.login.mockRejectedValueOnce({
            response: { data: { detail: 'Sai mật khẩu' } },
        })
        renderLogin()
        fireEvent.change(screen.getByLabelText(/email/i), {
            target: { value: 'test@example.com' },
        })
        fireEvent.change(screen.getByLabelText(/mật khẩu/i), {
            target: { value: 'wrong' },
        })
        fireEvent.click(screen.getByRole('button', { name: /đăng nhập/i }))
        await waitFor(() => {
            expect(screen.getByText('Sai mật khẩu')).toBeInTheDocument()
        })
    })
})
