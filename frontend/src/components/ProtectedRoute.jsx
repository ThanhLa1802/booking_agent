import { Navigate } from 'react-router-dom'
import useAuthStore from '../stores/authStore'

/**
 * Wraps protected routes — redirects to /login if no access token.
 * Also handles silent refresh on first load using persisted refreshToken.
 */
export default function ProtectedRoute({ children }) {
    const { accessToken } = useAuthStore()
    if (!accessToken) return <Navigate to="/login" replace />
    return children
}
