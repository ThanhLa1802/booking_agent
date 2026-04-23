import axios from 'axios'
import useAuthStore from '../stores/authStore'

const BASE_URL = import.meta.env.VITE_API_URL || ''

const apiClient = axios.create({
    baseURL: BASE_URL,
    headers: { 'Content-Type': 'application/json' },
})

// Attach access token to every request
apiClient.interceptors.request.use((config) => {
    const token = useAuthStore.getState().accessToken
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})

// Silent token refresh on 401
let refreshing = null  // deduplicate concurrent refresh calls

// Auth endpoints must never be intercepted — avoids double-counting failures for axes
const AUTH_ENDPOINTS = ['/api/auth/token/', '/api/auth/token/refresh/']

apiClient.interceptors.response.use(
    (response) => response,
    async (error) => {
        const original = error.config
        const isAuthEndpoint = AUTH_ENDPOINTS.some((p) => original.url?.includes(p))
        if (error.response?.status === 401 && !original._retry && !isAuthEndpoint) {
            original._retry = true
            try {
                if (!refreshing) {
                    const { refreshToken } = useAuthStore.getState()
                    if (!refreshToken) throw new Error('No refresh token')
                    // Use plain axios — avoid intercepting the refresh call itself
                    refreshing = axios
                        .post(`${BASE_URL}/api/auth/token/refresh/`, { refresh: refreshToken })
                        .then((res) => {
                            // Save both tokens — Django rotates refreshToken on every refresh
                            useAuthStore.getState().setTokens(res.data.access, res.data.refresh)
                            return res.data.access
                        })
                        .finally(() => {
                            refreshing = null
                        })
                }
                const newToken = await refreshing
                original.headers.Authorization = `Bearer ${newToken}`
                return apiClient(original)
            } catch {
                useAuthStore.getState().logout()
                window.location.href = '/login'
                return Promise.reject(error)
            }
        }
        return Promise.reject(error)
    }
)

export default apiClient
