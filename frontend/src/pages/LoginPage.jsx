import { useState } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import {
    Box,
    Button,
    Container,
    TextField,
    Typography,
    Alert,
    Paper,
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
        <Container maxWidth="sm">
            <Box
                sx={{
                    minHeight: '100vh',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                }}
            >
                <Paper elevation={3} sx={{ p: 4, width: '100%' }}>
                    <Typography variant="h5" fontWeight={700} gutterBottom align="center">
                        Trinity College London
                    </Typography>
                    <Typography variant="subtitle1" color="text.secondary" align="center" mb={3}>
                        Đăng nhập để đặt lịch thi
                    </Typography>

                    {location.state?.registered && (
                        <Alert severity="success" sx={{ mb: 2 }}>
                            Đăng ký thành công! Hãy đăng nhập.
                        </Alert>
                    )}
                    {error && (
                        <Alert severity="error" sx={{ mb: 2 }}>
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
                            margin="normal"
                            autoComplete="email"
                            autoFocus
                        />
                        <TextField
                            label="Mật khẩu"
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            fullWidth
                            required
                            margin="normal"
                            autoComplete="current-password"
                        />
                        <Button
                            type="submit"
                            variant="contained"
                            fullWidth
                            size="large"
                            disabled={loading}
                            sx={{ mt: 2 }}
                        >
                            {loading ? <CircularProgress size={24} /> : 'Đăng nhập'}
                        </Button>
                    </Box>
                    <Typography variant="body2" align="center" sx={{ mt: 2 }}>
                        Chưa có tài khoản?{' '}
                        <Link to="/register" style={{ color: 'inherit' }}>Đăng ký ngay</Link>
                    </Typography>
                </Paper>
            </Box>
        </Container>
    )
}
