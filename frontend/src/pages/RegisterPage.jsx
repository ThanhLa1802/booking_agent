import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
    Alert,
    Box,
    Button,
    CircularProgress,
    Container,
    MenuItem,
    Paper,
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
        <Container maxWidth="sm">
            <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Paper elevation={3} sx={{ p: 4, width: '100%' }}>
                    <Typography variant="h5" fontWeight={700} gutterBottom align="center">
                        Trinity College London
                    </Typography>
                    <Typography variant="subtitle1" color="text.secondary" align="center" mb={3}>
                        Tạo tài khoản mới
                    </Typography>

                    {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

                    <Box component="form" onSubmit={handleSubmit} noValidate>
                        <TextField
                            label="Tên đăng nhập"
                            name="username"
                            value={form.username}
                            onChange={handleChange}
                            fullWidth required margin="normal"
                            autoComplete="username" autoFocus
                        />
                        <TextField
                            label="Email"
                            name="email"
                            type="email"
                            value={form.email}
                            onChange={handleChange}
                            fullWidth required margin="normal"
                            autoComplete="email"
                        />
                        <TextField
                            label="Mật khẩu"
                            name="password"
                            type="password"
                            value={form.password}
                            onChange={handleChange}
                            fullWidth required margin="normal"
                            autoComplete="new-password"
                            inputProps={{ minLength: 8 }}
                        />
                        <TextField
                            label="Xác nhận mật khẩu"
                            name="confirmPassword"
                            type="password"
                            value={form.confirmPassword}
                            onChange={handleChange}
                            fullWidth required margin="normal"
                            autoComplete="new-password"
                        />
                        <TextField
                            select
                            label="Vai trò"
                            name="role"
                            value={form.role}
                            onChange={handleChange}
                            fullWidth margin="normal"
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
                            fullWidth margin="normal"
                            autoComplete="tel"
                        />
                        <Button
                            type="submit"
                            variant="contained"
                            fullWidth size="large"
                            disabled={loading}
                            sx={{ mt: 2 }}
                        >
                            {loading ? <CircularProgress size={24} /> : 'Đăng ký'}
                        </Button>
                    </Box>

                    <Typography variant="body2" align="center" sx={{ mt: 2 }}>
                        Đã có tài khoản?{' '}
                        <Link to="/login" style={{ color: 'inherit' }}>Đăng nhập</Link>
                    </Typography>
                </Paper>
            </Box>
        </Container>
    )
}
