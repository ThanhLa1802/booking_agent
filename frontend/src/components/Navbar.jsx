import { AppBar, Box, Button, Chip, Toolbar, Typography } from '@mui/material'
import MusicNoteOutlinedIcon from '@mui/icons-material/MusicNoteOutlined'
import AdminPanelSettingsOutlinedIcon from '@mui/icons-material/AdminPanelSettingsOutlined'
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined'
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
    <AppBar position="sticky">
      <Toolbar sx={{ gap: 1.5 }}>
        <MusicNoteOutlinedIcon sx={{ color: '#A0825C', fontSize: 22 }} />
        <Typography
          variant="body1"
          fontWeight={500}
          letterSpacing="-0.01em"
          sx={{ flexGrow: 1, userSelect: 'none' }}
        >
          Trinity
        </Typography>

        <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
          {isAdmin ? (
            <>
              <Button
                color="inherit"
                component={Link}
                to="/scheduling"
                startIcon={<AdminPanelSettingsOutlinedIcon />}
                sx={{ color: 'text.secondary', fontWeight: 400 }}
              >
                Lịch thi
              </Button>
              <Button
                color="inherit"
                component={Link}
                to="/chat"
                startIcon={<SmartToyOutlinedIcon />}
                sx={{ color: 'text.secondary', fontWeight: 400 }}
              >
                Trợ lý
              </Button>
            </>
          ) : (
            <>
              <Button
                color="inherit"
                component={Link}
                to="/catalog"
                sx={{ color: 'text.secondary', fontWeight: 400 }}
              >
                Danh mục
              </Button>
              <Button
                color="inherit"
                component={Link}
                to="/chat"
                sx={{ color: 'text.secondary', fontWeight: 400 }}
              >
                Trợ lý
              </Button>
              <Button
                color="inherit"
                component={Link}
                to="/bookings"
                sx={{ color: 'text.secondary', fontWeight: 400 }}
              >
                Lịch thi
              </Button>
            </>
          )}

          {user && (
            <Chip
              label={user.email}
              size="small"
              variant="outlined"
              sx={{
                ml: 1,
                color: 'text.secondary',
                borderColor: 'divider',
                fontWeight: 400,
                fontSize: '0.75rem',
              }}
            />
          )}

          <Button
            size="small"
            variant="outlined"
            onClick={handleLogout}
            sx={{ ml: 0.5 }}
          >
            Đăng xuất
          </Button>
        </Box>
      </Toolbar>
    </AppBar>
  )
}
