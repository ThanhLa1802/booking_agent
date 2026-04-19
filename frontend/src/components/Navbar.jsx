import { AppBar, Box, Button, Toolbar, Typography } from '@mui/material'
import MusicNoteIcon from '@mui/icons-material/MusicNote'
import { Link, useNavigate } from 'react-router-dom'
import useAuthStore from '../stores/authStore'

export default function Navbar() {
    const navigate = useNavigate()
    const { logout, user } = useAuthStore()

    const handleLogout = () => {
        logout()
        navigate('/login')
    }

    return (
        <AppBar position="sticky" elevation={1}>
            <Toolbar>
                <MusicNoteIcon sx={{ mr: 1 }} />
                <Typography variant="h6" fontWeight={700} sx={{ flexGrow: 1 }}>
                    Trinity Exam Booking
                </Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
                    <Button color="inherit" component={Link} to="/catalog">
                        Danh mục
                    </Button>
                    <Button color="inherit" component={Link} to="/chat">
                        Trợ lý AI
                    </Button>
                    <Button color="inherit" component={Link} to="/bookings">
                        Lịch thi của tôi
                    </Button>
                    {user && (
                        <Typography variant="body2" sx={{ alignSelf: 'center', opacity: 0.8, mx: 1 }}>
                            {user.email}
                        </Typography>
                    )}
                    <Button color="inherit" variant="outlined" size="small" onClick={handleLogout}>
                        Đăng xuất
                    </Button>
                </Box>
            </Toolbar>
        </AppBar>
    )
}
