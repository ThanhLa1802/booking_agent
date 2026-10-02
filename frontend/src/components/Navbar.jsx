import { AppBar, Box, Button, Chip, IconButton, Toolbar, Tooltip, Typography } from '@mui/material'
import MusicNoteOutlinedIcon from '@mui/icons-material/MusicNoteOutlined'
import AdminPanelSettingsOutlinedIcon from '@mui/icons-material/AdminPanelSettingsOutlined'
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined'
import LightModeOutlinedIcon from '@mui/icons-material/LightModeOutlined'
import DarkModeOutlinedIcon from '@mui/icons-material/DarkModeOutlined'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import useAuthStore from '../stores/authStore'
import useUiStore from '../stores/uiStore'

function NavLink({ to, children, icon }) {
  const { pathname } = useLocation()
  const active = pathname === to
  return (
    <Button
      component={Link}
      to={to}
      startIcon={icon}
      sx={{
        color: active ? 'primary.main' : 'text.secondary',
        fontWeight: active ? 600 : 400,
        '&:hover': { color: 'primary.main', backgroundColor: 'transparent' },
      }}
    >
      {children}
    </Button>
  )
}

export default function Navbar() {
  const navigate = useNavigate()
  const { logout, user } = useAuthStore()
  const mode = useUiStore((s) => s.mode)
  const toggleMode = useUiStore((s) => s.toggleMode)
  const isAdmin = user?.role === 'CENTER_ADMIN'

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <AppBar position="sticky">
      <Toolbar sx={{ gap: 1.5 }}>
        {/* Wordmark */}
        <Box
          component={Link}
          to={isAdmin ? '/scheduling' : '/catalog'}
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1.25,
            textDecoration: 'none',
            color: 'inherit',
            mr: 1,
          }}
        >
          <Box
            sx={{
              width: 32,
              height: 32,
              borderRadius: 1,
              display: 'grid',
              placeItems: 'center',
              bgcolor: 'primary.main',
              color: 'primary.contrastText',
            }}
          >
            <MusicNoteOutlinedIcon sx={{ fontSize: 18 }} />
          </Box>
          <Box sx={{ display: 'flex', flexDirection: 'column', lineHeight: 1 }}>
            <Typography
              component="span"
              sx={{ fontFamily: '"Playfair Display", serif', fontSize: '1.0625rem', fontWeight: 600 }}
            >
              Trinity
            </Typography>
            <Typography
              component="span"
              variant="overline"
              sx={{ color: 'text.secondary', fontSize: '0.5625rem', letterSpacing: '0.18em' }}
            >
              College London
            </Typography>
          </Box>
        </Box>

        <Box sx={{ flexGrow: 1 }} />

        <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
          {isAdmin ? (
            <>
              <NavLink to="/scheduling" icon={<AdminPanelSettingsOutlinedIcon fontSize="small" />}>
                Lịch thi
              </NavLink>
              <NavLink to="/chat" icon={<SmartToyOutlinedIcon fontSize="small" />}>
                Trợ lý
              </NavLink>
            </>
          ) : (
            <>
              <NavLink to="/catalog">Danh mục</NavLink>
              <NavLink to="/chat">Trợ lý</NavLink>
              <NavLink to="/bookings">Lịch thi</NavLink>
            </>
          )}

          {user?.email && (
            <Chip
              label={user.email}
              size="small"
              variant="outlined"
              sx={{
                ml: 1,
                color: 'text.secondary',
                borderColor: 'divider',
                fontWeight: 400,
                display: { xs: 'none', md: 'inline-flex' },
              }}
            />
          )}

          <Tooltip title={mode === 'light' ? 'Chế độ tối' : 'Chế độ sáng'}>
            <IconButton
              size="small"
              onClick={toggleMode}
              aria-label="Đổi chế độ màu"
              sx={{ ml: 0.5, color: 'text.secondary' }}
            >
              {mode === 'light' ? (
                <DarkModeOutlinedIcon fontSize="small" />
              ) : (
                <LightModeOutlinedIcon fontSize="small" />
              )}
            </IconButton>
          </Tooltip>

          <Button size="small" variant="outlined" onClick={handleLogout} sx={{ ml: 0.5 }}>
            Đăng xuất
          </Button>
        </Box>
      </Toolbar>
    </AppBar>
  )
}
