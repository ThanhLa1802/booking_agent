import { useState } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import {
  Box,
  Button,
  Container,
  TextField,
  Typography,
  Alert,
  CircularProgress,
} from '@mui/material'
import useAuthStore from '../stores/authStore'
import { login } from '../api'

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
    <Box
      sx={{
        minHeight: '100svh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        px: 2,
      }}
    >
      <Container maxWidth="xs" disableGutters>
        {/* Wordmark */}
        <Box sx={{ mb: 6, textAlign: 'center' }}>
          <Typography
            variant="h4"
            fontWeight={500}
            letterSpacing="-0.03em"
            mb={0.5}
          >
            Trinity College London
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Đặt lịch thi âm nhạc
          </Typography>
        </Box>

        {/* Alerts */}
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

        {/* Form */}
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
          <Button
            type="submit"
            variant="contained"
            fullWidth
            size="large"
            disabled={loading}
          >
            {loading ? (
              <CircularProgress size={20} sx={{ color: 'inherit' }} />
            ) : (
              'Đăng nhập'
            )}
          </Button>
        </Box>

        {/* Footer */}
        <Typography variant="body2" color="text.secondary" align="center" mt={3}>
          Chưa có tài khoản?{' '}
          <Link
            to="/register"
            style={{ color: '#A0825C', textDecoration: 'none', fontWeight: 500 }}
          >
            Đăng ký
          </Link>
        </Typography>
      </Container>
    </Box>
  )
}
