import { Box, Button, Typography } from '@mui/material'
import { alpha } from '@mui/material/styles'
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined'

/**
 * ConfirmBanner — confirmation gate for agent write actions.
 * A warm rule on the left, like a fermata held before resolution.
 */
export default function ConfirmBanner({ onConfirm, onCancel }) {
  return (
    <Box
      role="alertdialog"
      aria-label="Xác nhận hành động"
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 1.5,
        mb: 2,
        px: 2,
        py: 1.5,
        borderLeft: '3px solid',
        borderColor: 'warning.main',
        borderRadius: '0 8px 8px 0',
        bgcolor: (theme) =>
          alpha(theme.palette.warning.main, theme.palette.mode === 'dark' ? 0.12 : 0.08),
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
        <InfoOutlinedIcon sx={{ color: 'warning.main', fontSize: 18 }} />
        <Typography variant="body2" fontWeight={500}>
          Trợ lý cần bạn xác nhận để tiếp tục.
        </Typography>
      </Box>
      <Box sx={{ display: 'flex', gap: 1 }}>
        <Button size="small" variant="contained" onClick={onConfirm}>
          Xác nhận
        </Button>
        <Button size="small" variant="outlined" onClick={onCancel}>
          Hủy
        </Button>
      </Box>
    </Box>
  )
}
