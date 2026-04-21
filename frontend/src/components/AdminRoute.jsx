import { Navigate } from 'react-router-dom'
import { CircularProgress, Box } from '@mui/material'
import useAuthStore from '../stores/authStore'

/**
 * Wraps routes that require CENTER_ADMIN role.
 * Redirects non-admin authenticated users to /chat.
 */
export default function AdminRoute({ children }) {
    const { accessToken, user, isHydrating } = useAuthStore()

    if (isHydrating) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
                <CircularProgress />
            </Box>
        )
    }

    if (!accessToken) return <Navigate to="/login" replace />
    if (user?.role !== 'CENTER_ADMIN') return <Navigate to="/chat" replace />

    return children
}
