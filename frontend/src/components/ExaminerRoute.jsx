import { Navigate } from 'react-router-dom'
import { CircularProgress, Box } from '@mui/material'
import useAuthStore from '../stores/authStore'

/**
 * Wraps routes that require EXAMINER role.
 * Redirects other authenticated users to their own home.
 */
export default function ExaminerRoute({ children }) {
    const { accessToken, user, isHydrating } = useAuthStore()

    if (isHydrating) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100svh' }}>
                <CircularProgress size={28} thickness={3} />
            </Box>
        )
    }

    if (!accessToken) return <Navigate to="/login" replace />
    if (user?.role !== 'EXAMINER') {
        return <Navigate to={user?.role === 'CENTER_ADMIN' ? '/scheduling' : '/chat'} replace />
    }

    return children
}
