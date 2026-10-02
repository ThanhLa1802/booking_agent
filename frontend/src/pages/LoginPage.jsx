import { useState } from 'react'
import { useNavigate, useLocation, Link as RouterLink } from 'react-router-dom'
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Link,
  TextField,
  Typography,
} from '@mui/material'
import useAuthStore from '../stores/authStore'
import { login } from '../api'
import AuthLayout from '../components/AuthLayout'

export default function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { setTokens, setUser } = useAuthStore()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const res = await login(email, password)
      const { access, refresh, user } = res.data
      setTokens(access, refresh)
      if (user) setUser(user)
      const dest = user?.role === 'CENTER_ADMIN' ? '/scheduling' : '/chat'
      navigate(dest)
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        err.response?.data?.non_field_errors?.[0] ||
        'Đăng nhập thất bại. Vui lòng kiểm tra lại.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout
      eyebrow="Đăng nhập"
      title="Chào mừng trở lại"
      subtitle="Đăng nhập để tiếp tục đặt lịch thi."
    >
      {location.state?.registered && (
        <Alert severity="success" sx={{ mb: 3 }}>
          Đăng ký thành công! Hãy đăng nhập.
        </Alert>
      )}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <Box component="form" onSubmit={handleSubmit} noValidate>
        <TextField
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          fullWidth
          required
          autoComplete="email"
          autoFocus
          sx={{ mb: 2 }}
        />
        <TextField
          label="Mật khẩu"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          fullWidth
          required
          autoComplete="current-password"
          sx={{ mb: 3 }}
        />
        <Button type="submit" variant="contained" fullWidth size="large" disabled={loading}>
          {loading ? <CircularProgress size={20} sx={{ color: 'inherit' }} /> : 'Đăng nhập'}
        </Button>
      </Box>

      <Typography variant="body2" color="text.secondary" align="center" sx={{ mt: 3 }}>
        Chưa có tài khoản?{' '}
        <Link component={RouterLink} to="/register">
          Đăng ký
        </Link>
      </Typography>
    </AuthLayout>
  )
}
