import { Box, Button, Typography } from '@mui/material'

/**
 * ConfirmBanner — minimal confirmation gate.
 * A thin crimson left border like a rest mark in a score.
 */
export default function ConfirmBanner({ onConfirm, onCancel }) {
  return (
    <Box className="confirm-banner">
      <Typography variant="body2" color="text.primary" fontWeight={500}>
        Trợ lý cần bạn xác nhận để tiếp tục.
      </Typography>
      <Box sx={{ display: 'flex', gap: 1 }}>
        <Button
          size="small"
          variant="contained"
          onClick={onConfirm}
          sx={{
            bgcolor: '#5C8A67',
            '&:hover': { bgcolor: '#4A7355' },
          }}
        >
          Xác nhận
        </Button>
        <Button size="small" variant="outlined" onClick={onCancel}>
          Hủy
        </Button>
      </Box>
    </Box>
  )
}
