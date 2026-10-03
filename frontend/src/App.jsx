import { useEffect, useMemo } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { CssBaseline, ThemeProvider } from '@mui/material'
import { getTheme } from './theme'
import useUiStore from './stores/uiStore'
import useAuthStore from './stores/authStore'
import { refreshAccessToken } from './api'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import CatalogPage from './pages/CatalogPage'
import ChatPage from './pages/ChatPage'
import BookingsPage from './pages/BookingsPage'
import ProtectedRoute from './components/ProtectedRoute'
import AdminRoute from './components/AdminRoute'
import ExaminerRoute from './components/ExaminerRoute'
import SchedulingPage from './pages/SchedulingPage'
import MySchedulePage from './pages/MySchedulePage'
import ScheduleTaskPoller from './components/ScheduleTaskPoller'

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

export default function App() {
  const mode = useUiStore((s) => s.mode)
  const theme = useMemo(() => getTheme(mode), [mode])

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline enableColorScheme />
      <BrowserRouter>
        <TokenRefreshGate>
          <ScheduleTaskPoller />
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route
              path="/catalog"
              element={
                <ProtectedRoute>
                  <CatalogPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/chat"
              element={
                <ProtectedRoute>
                  <ChatPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/bookings"
              element={
                <ProtectedRoute>
                  <BookingsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/scheduling"
              element={
                <AdminRoute>
                  <SchedulingPage />
                </AdminRoute>
              }
            />
            <Route
              path="/my-schedule"
              element={
                <ExaminerRoute>
                  <MySchedulePage />
                </ExaminerRoute>
              }
            />
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="*" element={<Navigate to="/login" replace />} />
          </Routes>
        </TokenRefreshGate>
      </BrowserRouter>
    </ThemeProvider>
  )
}
