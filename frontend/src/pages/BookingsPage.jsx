import { useEffect } from 'react'
import {
    Alert,
    Box,
    Chip,
    CircularProgress,
    Container,
    Paper,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Typography,
} from '@mui/material'
import { getMyBookings } from '../api'
import useExamStore from '../stores/examStore'
import Navbar from '../components/Navbar'

const STATUS_COLOR = {
    confirmed: 'success',
    pending: 'warning',
    cancelled: 'error',
    completed: 'default',
}

const STATUS_LABEL = {
    confirmed: 'Đã xác nhận',
    pending: 'Chờ xác nhận',
    cancelled: 'Đã hủy',
    completed: 'Hoàn thành',
}

export default function BookingsPage() {
    const { slots: bookings, setSlots: setBookings, loading, error, setLoading, setError } =
        useExamStore()

    useEffect(() => {
        const fetch = async () => {
            setLoading(true)
            try {
                const res = await getMyBookings()
                setBookings(res.data || [])
            } catch (err) {
                setError(err.response?.data?.detail || 'Không thể tải lịch thi.')
            } finally {
                setLoading(false)
            }
        }
        fetch()
    }, [])

    return (
        <>
            <Navbar />
            <Container maxWidth="lg" sx={{ py: 4 }}>
                <Typography variant="h5" fontWeight={700} gutterBottom>
                    Lịch thi của tôi
                </Typography>

                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                {loading && (
                    <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
                        <CircularProgress />
                    </Box>
                )}

                {!loading && bookings.length === 0 && (
                    <Typography color="text.secondary">Bạn chưa có lịch thi nào.</Typography>
                )}

                {!loading && bookings.length > 0 && (
                    <TableContainer component={Paper} variant="outlined">
                        <Table size="small">
                            <TableHead>
                                <TableRow>
                                    <TableCell>Mã đặt lịch</TableCell>
                                    <TableCell>Môn thi</TableCell>
                                    <TableCell>Cấp độ</TableCell>
                                    <TableCell>Loại hình</TableCell>
                                    <TableCell>Ngày thi</TableCell>
                                    <TableCell>Giờ thi</TableCell>
                                    <TableCell>Lệ phí</TableCell>
                                    <TableCell>Trạng thái</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {bookings.map((b) => (
                                    <TableRow key={b.id} hover>
                                        <TableCell>#{b.id}</TableCell>
                                        <TableCell>{b.slot?.instrument || '—'}</TableCell>
                                        <TableCell>Grade {b.slot?.grade || '—'}</TableCell>
                                        <TableCell>{b.slot?.exam_type_display || b.slot?.exam_type || '—'}</TableCell>
                                        <TableCell>
                                            {b.slot?.exam_date
                                                ? new Date(b.slot.exam_date).toLocaleDateString('vi-VN')
                                                : '—'}
                                        </TableCell>
                                        <TableCell>{b.slot?.start_time || '—'}</TableCell>
                                        <TableCell>
                                            {b.slot?.fee ? `${Number(b.slot.fee).toLocaleString('vi-VN')}đ` : '—'}
                                        </TableCell>
                                        <TableCell>
                                            <Chip
                                                size="small"
                                                label={STATUS_LABEL[b.status] || b.status}
                                                color={STATUS_COLOR[b.status] || 'default'}
                                            />
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                )}
            </Container>
        </>
    )
}
