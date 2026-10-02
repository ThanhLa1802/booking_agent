import { useEffect, useState } from 'react'
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  Container,
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

const STATUS_CONFIG = {
  CONFIRMED: { label: 'Đã xác nhận', color: '#5C8A67' },
  PENDING: { label: 'Chờ xác nhận', color: '#C49450' },
  CANCELLED: { label: 'Đã huỷ', color: '#C25450' },
  COMPLETED: { label: 'Hoàn thành', color: '#707070' },
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
      <Container maxWidth="lg" sx={{ py: 5, px: { xs: 2, sm: 3 } }}>
        <Typography variant="h4" mb={1}>Lịch thi của tôi</Typography>
        <Typography variant="body2" color="text.secondary" mb={4}>
          Theo dõi các kỳ thi đã đăng ký
        </Typography>

        {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
            <CircularProgress size={28} />
          </Box>
        )}

        {!loading && bookings.length === 0 && (
          <Box className="empty-state">
            <Typography variant="body2">
              Bạn chưa có lịch thi nào.{' '}
              <a href="/catalog" style={{ color: '#A0825C', textDecoration: 'none', fontWeight: 500 }}>
                Xem danh mục
              </a>
            </Typography>
          </Box>
        )}

        {!loading && bookings.length > 0 && (
          <TableContainer sx={{ border: '1px solid #EBE9E6', borderRadius: 2 }}>
            <Table size="medium">
              <TableHead>
                <TableRow>
                  <TableCell>Mã đặt lịch</TableCell>
                  <TableCell>Học viên</TableCell>
                  <TableCell>Môn thi</TableCell>
                  <TableCell>Trung tâm</TableCell>
                  <TableCell>Ngày thi</TableCell>
                  <TableCell>Giờ</TableCell>
                  <TableCell>Thành phố</TableCell>
                  <TableCell>Trạng thái</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {bookings.map((b) => (
                  <TableRow key={b.id} hover>
                    <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '0.8125rem' }}>
                      #{b.id}
                    </TableCell>
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
                        label={STATUS_CONFIG[b.status]?.label || b.status}
                        sx={{
                          bgcolor: `${STATUS_CONFIG[b.status]?.color || '#707070'}14`,
                          color: STATUS_CONFIG[b.status]?.color || '#707070',
                          fontWeight: 500,
                          fontSize: '0.75rem',
                        }}
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
