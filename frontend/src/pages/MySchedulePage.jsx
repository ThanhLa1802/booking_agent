import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import CalendarMonthOutlinedIcon from '@mui/icons-material/CalendarMonthOutlined'
import RefreshIcon from '@mui/icons-material/Refresh'
import { alpha } from '@mui/material/styles'
import Navbar from '../components/Navbar'
import { getMyExaminerSchedule } from '../api'

const today = new Date()
const toIso = (d) => d.toISOString().split('T')[0]

function defaultRange() {
  const from = new Date(today.getFullYear(), today.getMonth(), 1)
  const to = new Date(today.getFullYear(), today.getMonth() + 1, 0)
  return { from: toIso(from), to: toIso(to) }
}

const STYLE_LABEL = {
  CLASSICAL_JAZZ: 'Classical & Jazz',
  ROCK_POP: 'Rock & Pop',
  THEORY: 'Theory',
}

const groupHeaderSx = {
  px: 2.5,
  py: 1.5,
  bgcolor: 'background.default',
  borderBottom: '1px solid',
  borderColor: 'divider',
}

export default function MySchedulePage() {
  const range = defaultRange()
  const [dateFrom, setDateFrom] = useState(range.from)
  const [dateTo, setDateTo] = useState(range.to)
  const [examiner, setExaminer] = useState(null)
  const [slots, setSlots] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await getMyExaminerSchedule({ date_from: dateFrom, date_to: dateTo })
      setExaminer(res.data?.examiner || null)
      setSlots(res.data?.slots || [])
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          'Không thể tải lịch thi của bạn. Vui lòng thử lại.'
      )
    } finally {
      setLoading(false)
    }
  }, [dateFrom, dateTo])

  // Initial + range-change fetch. fetchData is a stable async callback.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { fetchData() }, [fetchData])

  const grouped = slots.reduce((acc, s) => {
    if (!acc[s.exam_date]) acc[s.exam_date] = []
    acc[s.exam_date].push(s)
    return acc
  }, {})
  const sortedDates = Object.keys(grouped).sort()

  return (
    <>
      <Navbar />
      <Container maxWidth="lg" sx={{ py: { xs: 4, md: 6 }, px: { xs: 2, md: 4 } }}>
        <Stack direction="row" alignItems="flex-end" spacing={2} mb={4}>
          <Box flexGrow={1}>
            <Typography variant="overline" color="primary.main">
              Giám khảo
            </Typography>
            <Typography variant="h2">Lịch thi của tôi</Typography>
            <Typography variant="body1" color="text.secondary" mt={0.5}>
              {examiner
                ? `${examiner.name} · ${examiner.center_name}, ${examiner.center_city}`
                : 'Các ca thi được phân công cho bạn.'}
            </Typography>
          </Box>
          <Tooltip title="Làm mới">
            <span>
              <Button
                variant="outlined"
                size="small"
                onClick={fetchData}
                disabled={loading}
                startIcon={<RefreshIcon />}
              >
                Làm mới
              </Button>
            </span>
          </Tooltip>
        </Stack>

        {examiner && (
          <Stack direction="row" spacing={1.5} mb={3} flexWrap="wrap" useFlexGap>
            <Chip label={`${slots.length} ca thi`} size="small" />
            <Chip
              label={`Tối đa ${examiner.max_exams_per_day} ca/ngày`}
              size="small"
              variant="outlined"
            />
            {examiner.specialization_names?.map((s) => (
              <Chip key={s} label={s} size="small" variant="outlined" color="primary" />
            ))}
          </Stack>
        )}

        <Paper variant="outlined" sx={{ p: 2.5, mb: 3 }}>
          <Stack direction="row" spacing={2} flexWrap="wrap" alignItems="center" useFlexGap>
            <TextField
              label="Từ ngày"
              type="date"
              size="small"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              InputLabelProps={{ shrink: true }}
              sx={{ minWidth: 170 }}
            />
            <TextField
              label="Đến ngày"
              type="date"
              size="small"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              InputLabelProps={{ shrink: true }}
              sx={{ minWidth: 170 }}
            />
            <Button variant="contained" onClick={fetchData} disabled={loading}>
              Tìm kiếm
            </Button>
          </Stack>
        </Paper>

        {error && (
          <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}>
            <CircularProgress size={28} thickness={3} />
          </Box>
        ) : slots.length === 0 ? (
          <Paper variant="outlined" sx={{ p: 5, textAlign: 'center' }}>
            <CalendarMonthOutlinedIcon sx={{ fontSize: 32, color: 'text.disabled', mb: 1 }} />
            <Typography color="text.secondary">
              Không có ca thi nào trong khoảng thời gian này.
            </Typography>
          </Paper>
        ) : (
          <Stack spacing={3}>
            {sortedDates.map((date) => (
              <Paper key={date} variant="outlined" sx={{ overflow: 'hidden' }}>
                <Box sx={groupHeaderSx}>
                  <Typography
                    variant="overline"
                    sx={{ fontSize: '0.6875rem', letterSpacing: '0.08em' }}
                  >
                    {new Date(date + 'T00:00:00').toLocaleDateString('vi-VN', {
                      weekday: 'long',
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                    })}
                  </Typography>
                </Box>

                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Giờ</TableCell>
                        <TableCell>Ca thi</TableCell>
                        <TableCell>Trung tâm</TableCell>
                        <TableCell>Loại</TableCell>
                        <TableCell align="center">Đã đặt</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {grouped[date].map((slot) => (
                        <TableRow
                          key={slot.id}
                          hover
                          sx={{
                            bgcolor: slot.examiner_id
                              ? 'inherit'
                              : (theme) => alpha(theme.palette.warning.main, 0.05),
                          }}
                        >
                          <TableCell
                            sx={{ whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}
                          >
                            {slot.start_time?.substring(0, 5)}
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" fontWeight={500}>
                              {slot.course_name}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">{slot.center_name}</Typography>
                            <Typography variant="caption" color="text.secondary">
                              {slot.center_city}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={STYLE_LABEL[slot.style] || slot.style}
                              size="small"
                              variant="outlined"
                            />
                          </TableCell>
                          <TableCell align="center">
                            <Typography
                              variant="body2"
                              sx={{ fontVariantNumeric: 'tabular-nums' }}
                            >
                              {slot.capacity - slot.available_capacity}/{slot.capacity}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Paper>
            ))}
          </Stack>
        )}
      </Container>
    </>
  )
}
