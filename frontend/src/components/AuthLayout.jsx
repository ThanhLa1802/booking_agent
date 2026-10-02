import { Box, Typography } from '@mui/material'
import MusicNoteOutlinedIcon from '@mui/icons-material/MusicNoteOutlined'

/**
 * AuthLayout — split editorial shell for login / register.
 * Left: brand statement (hidden on small screens). Right: the form.
 */
export default function AuthLayout({ eyebrow, title, subtitle, children }) {
  return (
    <Box sx={{ display: 'flex', minHeight: '100svh' }}>
      {/* ── Brand panel ─────────────────────────────────────────── */}
      <Box
        sx={{
          display: { xs: 'none', md: 'flex' },
          flexDirection: 'column',
          justifyContent: 'space-between',
          width: '46%',
          p: 6,
          bgcolor: 'background.default',
          borderRight: '1px solid',
          borderColor: 'divider',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* Mark */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Box
            sx={{
              width: 36,
              height: 36,
              borderRadius: 1,
              display: 'grid',
              placeItems: 'center',
              bgcolor: 'primary.main',
              color: 'primary.contrastText',
            }}
          >
            <MusicNoteOutlinedIcon sx={{ fontSize: 20 }} />
          </Box>
          <Typography
            sx={{ fontFamily: '"Playfair Display", serif', fontWeight: 600, fontSize: '1.125rem' }}
          >
            Trinity
          </Typography>
        </Box>

        {/* Statement */}
        <Box sx={{ maxWidth: 460 }}>
          <Typography variant="overline" color="primary.main">
            Trinity College London
          </Typography>
          <Typography variant="h2" sx={{ mt: 2, mb: 2.5 }}>
            Đặt lịch thi âm nhạc, cùng trợ lý AI.
          </Typography>
          <Box sx={{ width: 56, height: 2, bgcolor: 'primary.main', mb: 3 }} />
          <Typography variant="body1" color="text.secondary">
            Tra cứu chương trình, kiểm tra chỗ trống và hoàn tất đăng ký
            trong một cuộc trò chuyện.
          </Typography>
        </Box>

        <Typography variant="caption" color="text.secondary">
          © {new Date().getFullYear()} Trinity College London — Vietnam
        </Typography>
      </Box>

      {/* ── Form panel ──────────────────────────────────────────── */}
      <Box
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          px: { xs: 2.5, sm: 4 },
          py: 6,
        }}
      >
        <Box sx={{ width: '100%', maxWidth: 400 }}>
          {/* Mobile brand */}
          <Box sx={{ display: { xs: 'block', md: 'none' }, textAlign: 'center', mb: 4 }}>
            <Box
              sx={{
                width: 40,
                height: 40,
                mx: 'auto',
                mb: 1.5,
                borderRadius: 1,
                display: 'grid',
                placeItems: 'center',
                bgcolor: 'primary.main',
                color: 'primary.contrastText',
              }}
            >
              <MusicNoteOutlinedIcon sx={{ fontSize: 22 }} />
            </Box>
            <Typography sx={{ fontFamily: '"Playfair Display", serif', fontWeight: 600 }}>
              Trinity College London
            </Typography>
          </Box>

          {eyebrow && (
            <Typography variant="overline" color="primary.main">
              {eyebrow}
            </Typography>
          )}
          <Typography variant="h3" sx={{ mb: 0.5 }}>
            {title}
          </Typography>
          {subtitle && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3.5 }}>
              {subtitle}
            </Typography>
          )}

          {children}
        </Box>
      </Box>
    </Box>
  )
}
