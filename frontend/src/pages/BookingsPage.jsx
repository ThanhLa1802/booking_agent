import { useEffect, useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  Container,
  Link,
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

const STATUS_CONFIG = {
  CONFIRMED: { label: 'Đã xác nhận', color: 'success.main' },
  PENDING: { label: 'Chờ xác nhận', color: 'warning.main' },
  CANCELLED: { label: 'Đã huỷ', color: 'error.main' },
  COMPLETED: { label: 'Hoàn thành', color: 'text.secondary' },
}

function StatusChip({ status }) {
  const cfg = STATUS_CONFIG[status] || { label: status, color: 'text.secondary' }
  return (
    <Chip
      size="small"
      variant="outlined"
      label={cfg.label}
      sx={{
        color: cfg.color,
        borderColor: cfg.color,
        fontWeight: 500,
      }}
    />
  )
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

  const fmtDate = (d) => (d ? new Date(d).toLocaleDateString('vi-VN') : '—')

  return (
    <>
      <Navbar />
      <Container maxWidth="lg" sx={{ py: { xs: 4, md: 6 }, px: { xs: 2, sm: 3 } }}>
        {/* Header */}
        <Box sx={{ mb: 4 }}>
          <Typography variant="overline" color="primary.main">
            Đăng ký
          </Typography>
          <Typography variant="h2" sx={{ mb: 1 }}>
            Lịch thi của tôi
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Theo dõi các kỳ thi bạn đã đăng ký.
          </Typography>
        </Box>

        {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}>
            <CircularProgress size={28} thickness={3} />
          </Box>
        )}

        {!loading && bookings.length === 0 && (
          <Box sx={{ textAlign: 'center', py: 10, color: 'text.secondary' }}>
            <Typography variant="body1" sx={{ mb: 0.5 }}>
              Bạn chưa có lịch thi nào.
            </Typography>
            <Typography variant="body2">
              <Link component={RouterLink} to="/catalog">
                Xem danh mục kỳ thi
              </Link>
            </Typography>
          </Box>
        )}

        {!loading && bookings.length > 0 && (
          <>
            {/* Desktop table */}
            <TableContainer
              component={Paper}
              variant="outlined"
              sx={{ display: { xs: 'none', md: 'block' } }}
            >
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Mã</TableCell>
                    <TableCell>Học viên</TableCell>
                    <TableCell>Môn thi</TableCell>
                    <TableCell>Trung tâm</TableCell>
                    <TableCell>Ngày thi</TableCell>
                    <TableCell>Giờ</TableCell>
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
                      <TableCell>
                        {b.slot_detail?.center || '—'}
                        {b.slot_detail?.city ? (
                          <Typography variant="caption" color="text.secondary" display="block">
                            {b.slot_detail.city}
                          </Typography>
                        ) : null}
                      </TableCell>
                      <TableCell>{fmtDate(b.slot_detail?.exam_date)}</TableCell>
                      <TableCell>{b.slot_detail?.start_time || '—'}</TableCell>
                      <TableCell>
                        <StatusChip status={b.status} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>

            {/* Mobile cards */}
            <Box sx={{ display: { xs: 'flex', md: 'none' }, flexDirection: 'column', gap: 2 }}>
              {bookings.map((b) => (
                <Paper key={b.id} variant="outlined" sx={{ p: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1, mb: 1 }}>
                    <Typography variant="h6">{b.slot_detail?.course || '—'}</Typography>
                    <StatusChip status={b.status} />
                  </Box>
                  <Typography variant="body2" color="text.secondary">
                    {b.student_name} · #{b.id}
                  </Typography>
                  <Typography variant="body2" sx={{ mt: 0.5 }}>
                    {fmtDate(b.slot_detail?.exam_date)} · {b.slot_detail?.start_time || '—'}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {b.slot_detail?.center || '—'}
                    {b.slot_detail?.city ? `, ${b.slot_detail.city}` : ''}
                  </Typography>
                </Paper>
              ))}
            </Box>
          </>
        )}
      </Container>
    </>
  )
}
