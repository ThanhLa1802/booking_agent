import apiClient from './client'

// Auth — all go to Django (:8000 via proxy)
export const login = (email, password) =>
    apiClient.post('/api/auth/token/', { email, password })

export const refreshAccessToken = (refresh) =>
    apiClient.post('/api/auth/token/refresh/', { refresh })

// Catalog — FastAPI (:8001 via proxy)
export const getCourses = (params) =>
    apiClient.get('/api/catalog/courses', { params })

export const getSlots = (params) =>
    apiClient.get('/api/catalog/slots', { params })

// Bookings — FastAPI reads
export const getMyBookings = () => apiClient.get('/api/bookings/')

export const getBookingDetail = (id) => apiClient.get(`/api/bookings/${id}`)

// Agent — FastAPI SSE (returns raw fetch, not axios, for streaming)
export const createChatStream = (message, sessionId, accessToken) => {
    const url = `${import.meta.env.VITE_API_URL || ''}/api/agent/chat`
    return fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ message, session_id: sessionId }),
    })
}
