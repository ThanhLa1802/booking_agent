import { useEffect } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { CssBaseline, ThemeProvider, createTheme } from '@mui/material'
import '@fontsource/roboto/300.css'
import '@fontsource/roboto/400.css'
import '@fontsource/roboto/500.css'
import '@fontsource/roboto/700.css'
import useAuthStore from './stores/authStore'
import { refreshAccessToken } from './api'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import CatalogPage from './pages/CatalogPage'
import ChatPage from './pages/ChatPage'
import BookingsPage from './pages/BookingsPage'
import ProtectedRoute from './components/ProtectedRoute'
import AdminRoute from './components/AdminRoute'
import SchedulingPage from './pages/SchedulingPage'

const theme = createTheme({
  palette: {
    primary: { main: '#1565c0' },
    secondary: { main: '#6a1b9a' },
  },
})

function TokenRefreshGate({ children }) {
  const { refreshToken, setTokens, setHydrated, logout } = useAuthStore()

  useEffect(() => {
    if (!refreshToken) {
      setHydrated()
      return
    }
    refreshAccessToken(refreshToken)
      .then((res) => setTokens(res.data.access, res.data.refresh))
      .catch(() => logout())
      .finally(() => setHydrated())
  }, [])

  return children
}

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <TokenRefreshGate>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/catalog" element={<ProtectedRoute><CatalogPage /></ProtectedRoute>} />
            <Route path="/chat" element={<ProtectedRoute><ChatPage /></ProtectedRoute>} />
            <Route path="/bookings" element={<ProtectedRoute><BookingsPage /></ProtectedRoute>} />
            <Route path="/scheduling" element={<AdminRoute><SchedulingPage /></AdminRoute>} />
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="*" element={<Navigate to="/login" replace />} />
          </Routes>
        </TokenRefreshGate>
      </BrowserRouter>
    </ThemeProvider>
  )
}


export default App

