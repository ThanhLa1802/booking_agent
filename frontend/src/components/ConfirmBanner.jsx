import { Box, Button, Paper, Typography } from '@mui/material'
import { CheckCircleOutline as CheckCircleOutlineIcon, CancelOutlined as CancelOutlinedIcon } from '@mui/icons-material'

/**
 * ConfirmBanner — shown when agent requires explicit confirmation
 * before a write action (create_booking, cancel_booking).
 */
export default function ConfirmBanner({ onConfirm, onCancel }) {
    return (
        <Paper
            variant="outlined"
            sx={{
                p: 2,
                mb: 2,
                borderColor: 'warning.main',
                bgcolor: 'warning.50',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: 1,
            }}
        >
            <Typography variant="body2" fontWeight={500}>
                ⚠️ Trợ lý cần xác nhận của bạn để thực hiện thao tác này.
            </Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
                <Button
                    size="small"
                    variant="contained"
                    color="success"
                    startIcon={<CheckCircleOutlineIcon />}
                    onClick={onConfirm}
                >
                    Xác nhận
                </Button>
                <Button
                    size="small"
                    variant="outlined"
                    color="error"
                    startIcon={<CancelOutlinedIcon />}
                    onClick={onCancel}
                >
                    Hủy
                </Button>
            </Box>
        </Paper>
    )
}
