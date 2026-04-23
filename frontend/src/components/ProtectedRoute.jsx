import { Navigate } from 'react-router-dom'
import { CircularProgress, Box } from '@mui/material'
import useAuthStore from '../stores/authStore'

/**
 * Wraps protected routes — waits for token hydration before deciding.
 * Shows spinner while refresh is in-flight to prevent false redirect on F5.
 */
export default function ProtectedRoute({ children }) {
    const { accessToken, isHydrating } = useAuthStore()

    if (isHydrating) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
                <CircularProgress />
            </Box>
        )
    }

    if (!accessToken) return <Navigate to="/login" replace />
    return children
}
