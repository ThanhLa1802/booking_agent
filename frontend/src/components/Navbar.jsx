import { AppBar, Box, Button, Chip, Toolbar, Typography } from '@mui/material'
import MusicNoteIcon from '@mui/icons-material/MusicNote'
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings'
import SmartToyIcon from '@mui/icons-material/SmartToy'
import { Link, useNavigate } from 'react-router-dom'
import useAuthStore from '../stores/authStore'

export default function Navbar() {
    const navigate = useNavigate()
    const { logout, user } = useAuthStore()
    const isAdmin = user?.role === 'CENTER_ADMIN'

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
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                    {isAdmin ? (
                        /* Admin-only navigation */
                        <>
                            <Button
                                color="inherit"
                                component={Link}
                                to="/scheduling"
                                startIcon={<AdminPanelSettingsIcon />}
                            >
                                Quản lý lịch thi
                            </Button>
                            <Button
                                color="inherit"
                                component={Link}
                                to="/chat"
                                startIcon={<SmartToyIcon />}
                            >
                                Trợ lý AI
                            </Button>
                        </>
                    ) : (
                        /* Student/Parent navigation */
                        <>
                            <Button color="inherit" component={Link} to="/catalog">
                                Danh mục
                            </Button>
                            <Button color="inherit" component={Link} to="/chat">
                                Trợ lý AI
                            </Button>
                            <Button color="inherit" component={Link} to="/bookings">
                                Lịch thi của tôi
                            </Button>
                        </>
                    )}
                    {user && (
                        <Chip
                            label={`${user.email}${isAdmin ? ' · Admin' : ''}`}
                            size="small"
                            sx={{ color: 'white', borderColor: 'rgba(255,255,255,0.5)', ml: 1 }}
                            variant="outlined"
                        />
                    )}
                    <Button color="inherit" variant="outlined" size="small" onClick={handleLogout}>
                        Đăng xuất
                    </Button>
                </Box>
            </Toolbar>
        </AppBar>
    )
}
