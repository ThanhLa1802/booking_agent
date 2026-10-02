import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Container,
  MenuItem,
  TextField,
  Typography,
} from '@mui/material'
import apiClient from '../api/client'

const ROLES = [
  { value: 'STUDENT', label: 'Học viên' },
  { value: 'PARENT', label: 'Phụ huynh' },
]

export default function RegisterPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    role: 'STUDENT',
    phone: '',
  })
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleChange = (e) =>
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)

    if (form.password !== form.confirmPassword) {
      setError('Mật khẩu xác nhận không khớp.')
      return
    }

    setLoading(true)
    try {
      await apiClient.post('/api/auth/register/', {
        username: form.username,
        email: form.email,
        password: form.password,
        role: form.role,
        phone: form.phone,
      })
      navigate('/login', { state: { registered: true } })
    } catch (err) {
      const data = err.response?.data
      if (data && typeof data === 'object') {
        const msgs = Object.values(data).flat().join(' ')
        setError(msgs)
      } else {
        setError('Đăng ký thất bại. Vui lòng thử lại.')
      }
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
        <Box sx={{ mb: 5, textAlign: 'center' }}>
          <Typography
            variant="h4"
            fontWeight={500}
            letterSpacing="-0.03em"
            mb={0.5}
          >
            Trinity College London
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Tạo tài khoản mới
          </Typography>
        </Box>

        {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

        <Box component="form" onSubmit={handleSubmit} noValidate>
          <TextField
            label="Tên đăng nhập"
            name="username"
            value={form.username}
            onChange={handleChange}
            fullWidth
            required
            autoComplete="username"
            autoFocus
            sx={{ mb: 2 }}
          />
          <TextField
            label="Email"
            name="email"
            type="email"
            value={form.email}
            onChange={handleChange}
            fullWidth
            required
            autoComplete="email"
            sx={{ mb: 2 }}
          />
          <TextField
            label="Mật khẩu"
            name="password"
            type="password"
            value={form.password}
            onChange={handleChange}
            fullWidth
            required
            autoComplete="new-password"
            inputProps={{ minLength: 8 }}
            sx={{ mb: 2 }}
          />
          <TextField
            label="Xác nhận mật khẩu"
            name="confirmPassword"
            type="password"
            value={form.confirmPassword}
            onChange={handleChange}
            fullWidth
            required
            autoComplete="new-password"
            sx={{ mb: 2 }}
          />
          <TextField
            select
            label="Vai trò"
            name="role"
            value={form.role}
            onChange={handleChange}
            fullWidth
            sx={{ mb: 2 }}
          >
            {ROLES.map((r) => (
              <MenuItem key={r.value} value={r.value}>{r.label}</MenuItem>
            ))}
          </TextField>
          <TextField
            label="Số điện thoại (tuỳ chọn)"
            name="phone"
            value={form.phone}
            onChange={handleChange}
            fullWidth
            autoComplete="tel"
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
              'Đăng ký'
            )}
          </Button>
        </Box>

        <Typography variant="body2" color="text.secondary" align="center" mt={3}>
          Đã có tài khoản?{' '}
          <Link
            to="/login"
            style={{ color: '#A0825C', textDecoration: 'none', fontWeight: 500 }}
          >
            Đăng nhập
          </Link>
        </Typography>
      </Container>
    </Box>
  )
}
