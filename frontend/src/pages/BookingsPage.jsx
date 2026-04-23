import { useEffect, useState } from 'react'
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
import Navbar from '../components/Navbar'

const STATUS_COLOR = {
    CONFIRMED: 'success',
    PENDING: 'warning',
    CANCELLED: 'error',
    COMPLETED: 'default',
}

const STATUS_LABEL = {
    CONFIRMED: 'Đã xác nhận',
    PENDING: 'Chờ xác nhận',
    CANCELLED: 'Đã hủy',
    COMPLETED: 'Hoàn thành',
}

export default function BookingsPage() {
    const [bookings, setBookings] = useState([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    useEffect(() => {
        const fetch = async () => {
            setLoading(true)
            setError(null)
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
                                    <TableCell>Học viên</TableCell>
                                    <TableCell>Môn thi</TableCell>
                                    <TableCell>Trung tâm</TableCell>
                                    <TableCell>Ngày thi</TableCell>
                                    <TableCell>Giờ thi</TableCell>
                                    <TableCell>Thành phố</TableCell>
                                    <TableCell>Trạng thái</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {bookings.map((b) => (
                                    <TableRow key={b.id} hover>
                                        <TableCell>#{b.id}</TableCell>
                                        <TableCell>{b.student_name}</TableCell>
                                        <TableCell>{b.slot_detail?.course || '—'}</TableCell>
                                        <TableCell>{b.slot_detail?.center || '—'}</TableCell>
                                        <TableCell>
                                            {b.slot_detail?.exam_date
                                                ? new Date(b.slot_detail.exam_date).toLocaleDateString('vi-VN')
                                                : '—'}
                                        </TableCell>
                                        <TableCell>{b.slot_detail?.start_time || '—'}</TableCell>
                                        <TableCell>{b.slot_detail?.city || '—'}</TableCell>
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
