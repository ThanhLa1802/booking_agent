import { useState } from 'react'
import { useNavigate, Link as RouterLink } from 'react-router-dom'
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Link,
  MenuItem,
  TextField,
  Typography,
} from '@mui/material'
import apiClient from '../api/client'
import AuthLayout from '../components/AuthLayout'

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
    <AuthLayout
      eyebrow="Tạo tài khoản"
      title="Bắt đầu hành trình âm nhạc"
      subtitle="Chỉ mất một phút để bắt đầu."
    >
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

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
        <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
          <TextField
            select
            label="Vai trò"
            name="role"
            value={form.role}
            onChange={handleChange}
            sx={{ flex: '1 1 140px' }}
          >
            {ROLES.map((r) => (
              <MenuItem key={r.value} value={r.value}>
                {r.label}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Số điện thoại (tuỳ chọn)"
            name="phone"
            value={form.phone}
            onChange={handleChange}
            autoComplete="tel"
            sx={{ flex: '1 1 180px' }}
          />
        </Box>
        <Button type="submit" variant="contained" fullWidth size="large" disabled={loading}>
          {loading ? <CircularProgress size={20} sx={{ color: 'inherit' }} /> : 'Đăng ký'}
        </Button>
      </Box>

      <Typography variant="body2" color="text.secondary" align="center" sx={{ mt: 3 }}>
        Đã có tài khoản?{' '}
        <Link component={RouterLink} to="/login">
          Đăng nhập
        </Link>
      </Typography>
    </AuthLayout>
  )
}
