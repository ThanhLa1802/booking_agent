import { useEffect, useState, useCallback } from 'react'
import {
  Alert,
  Avatar,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  List,
  ListItemButton,
  ListItemText,
  Paper,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import { alpha } from '@mui/material/styles'
import CalendarMonthOutlinedIcon from '@mui/icons-material/CalendarMonthOutlined'
import PeopleAltOutlinedIcon from '@mui/icons-material/PeopleAltOutlined'
import PersonAddOutlinedIcon from '@mui/icons-material/PersonAddOutlined'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import RefreshIcon from '@mui/icons-material/Refresh'
import Navbar from '../components/Navbar'
import AddExaminerDialog from '../components/AddExaminerDialog'
import {
  assignExaminer,
  getSchedulingCalendar,
  getSchedulingExaminers,
  suggestExaminers,
} from '../api'

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

export default function SchedulingPage() {
  const range = defaultRange()
  const [activeTab, setActiveTab] = useState(0)
  const [dateFrom, setDateFrom] = useState(range.from)
  const [dateTo, setDateTo] = useState(range.to)

  const [slots, setSlots] = useState([])
  const [examiners, setExaminers] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)

  // Assign dialog state
  const [dialogSlot, setDialogSlot] = useState(null)
  const [suggestions, setSuggestions] = useState([])
  const [suggLoading, setSuggLoading] = useState(false)
  const [selectedExaminer, setSelectedExaminer] = useState(null)
  const [confirming, setConfirming] = useState(false)

  // Add-examiner dialog state
  const [addOpen, setAddOpen] = useState(false)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [calRes, exRes] = await Promise.all([
        getSchedulingCalendar({ date_from: dateFrom, date_to: dateTo }),
        getSchedulingExaminers(),
      ])
      setSlots(calRes.data || [])
      setExaminers(exRes.data || [])
    } catch (err) {
      setError(err.response?.data?.detail || 'Không thể tải dữ liệu lịch thi.')
    } finally {
      setLoading(false)
    }
  }, [dateFrom, dateTo])

  // Initial + range-change fetch. fetchData is a stable async callback.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { fetchData() }, [fetchData])

  const handleOpenAssign = async (slot) => {
    setDialogSlot(slot)
    setSelectedExaminer(null)
    setSuggestions([])
    setSuggLoading(true)
    try {
      const res = await suggestExaminers(slot.id)
      setSuggestions(res.data || [])
    } catch {
      setSuggestions([])
    } finally {
      setSuggLoading(false)
    }
  }

  const handleAssign = async () => {
    if (!selectedExaminer || !dialogSlot) return
    setConfirming(true)
    try {
      await assignExaminer(dialogSlot.id, selectedExaminer.examiner.id)
      setSuccess(`Đã phân công ${selectedExaminer.examiner.name} vào slot ${dialogSlot.id}`)
      setDialogSlot(null)
      fetchData()
    } catch (err) {
      setError(err.response?.data?.detail || 'Phân công thất bại.')
      setDialogSlot(null)
    } finally {
      setConfirming(false)
    }
  }

  const grouped = slots.reduce((acc, s) => {
    const key = s.exam_date
    if (!acc[key]) acc[key] = []
    acc[key].push(s)
    return acc
  }, {})
  const sortedDates = Object.keys(grouped).sort()

  const examinersByCenter = examiners.reduce((acc, e) => {
    const key = `${e.center_name} — ${e.center_city}`
    if (!acc[key]) acc[key] = []
    acc[key].push(e)
    return acc
  }, {})

  const assignedCount = slots.filter((s) => s.examiner_id).length

  return (
    <>
      <Navbar />
      <Container maxWidth="xl" sx={{ py: { xs: 4, md: 6 }, px: { xs: 2, md: 4 } }}>
        {/* Header */}
        <Stack direction="row" alignItems="flex-end" spacing={2} mb={4}>
          <Box flexGrow={1}>
            <Typography variant="overline" color="primary.main">
              Trung tâm
            </Typography>
            <Typography variant="h2">Quản lý lịch thi</Typography>
            <Typography variant="body1" color="text.secondary" mt={0.5}>
              Phân công giám khảo cho các ca thi.
            </Typography>
          </Box>
          <Button
            variant="contained"
            startIcon={<PersonAddOutlinedIcon />}
            onClick={() => setAddOpen(true)}
          >
            Thêm giám khảo
          </Button>
          <Tooltip title="Làm mới">
            <IconButton onClick={fetchData} disabled={loading} size="small">
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Stack>

        {/* Stats */}
        {!loading && slots.length > 0 && (
          <Stack direction="row" spacing={1.5} mb={3} flexWrap="wrap" useFlexGap>
            <Chip label={`${slots.length} ca thi`} size="small" />
            <Chip label={`${assignedCount} đã phân công`} size="small" color="success" variant="outlined" />
            <Chip
              label={`${slots.length - assignedCount} chưa phân công`}
              size="small"
              color="warning"
              variant="outlined"
            />
          </Stack>
        )}

        {/* Tabs */}
        <Paper variant="outlined" sx={{ mb: 3 }}>
          <Tabs value={activeTab} onChange={(_, v) => setActiveTab(v)} sx={{ px: 1 }}>
            <Tab
              icon={<CalendarMonthOutlinedIcon sx={{ fontSize: 18 }} />}
              iconPosition="start"
              label="Lịch thi"
              sx={{ minHeight: 48 }}
            />
            <Tab
              icon={<PeopleAltOutlinedIcon sx={{ fontSize: 18 }} />}
              iconPosition="start"
              label={`Giám khảo${examiners.length ? ` (${examiners.length})` : ''}`}
              sx={{ minHeight: 48 }}
            />
          </Tabs>
        </Paper>

        {/* Alerts */}
        {error && (
          <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        {success && (
          <Alert severity="success" onClose={() => setSuccess(null)} sx={{ mb: 2 }}>
            {success}
          </Alert>
        )}

        {/* ── TAB 0: Lịch thi ──────────────────────────────────── */}
        {activeTab === 0 && (
          <>
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

            {loading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}>
                <CircularProgress size={28} thickness={3} />
              </Box>
            ) : slots.length === 0 ? (
              <Paper variant="outlined" sx={{ p: 5, textAlign: 'center' }}>
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
                            <TableCell>Giám khảo</TableCell>
                            <TableCell align="center" sx={{ width: 80 }} />
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {grouped[date].map((slot) => (
                            <TableRow
                              key={slot.id}
                              hover
                              sx={{
                                bgcolor: (!slot.examiner_id)
                                  ? (theme) => alpha(theme.palette.warning.main, 0.05)
                                  : 'inherit',
                              }}
                            >
                              <TableCell sx={{ whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>
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
                                <Typography variant="body2" sx={{ fontVariantNumeric: 'tabular-nums' }}>
                                  {slot.capacity - slot.available_capacity}/{slot.capacity}
                                </Typography>
                              </TableCell>
                              <TableCell>
                                {slot.examiner_name ? (
                                  <Stack direction="row" alignItems="center" spacing={0.75}>
                                    <CheckCircleIcon sx={{ fontSize: 16, color: 'success.main' }} />
                                    <Typography variant="body2">{slot.examiner_name}</Typography>
                                  </Stack>
                                ) : (
                                  <Typography variant="body2" sx={{ color: 'warning.main', fontStyle: 'italic' }}>
                                    Chưa phân công
                                  </Typography>
                                )}
                              </TableCell>
                              <TableCell align="center">
                                <Tooltip title="Phân công giám khảo">
                                  <IconButton
                                    size="small"
                                    onClick={() => handleOpenAssign(slot)}
                                    sx={{ color: slot.examiner_id ? 'text.secondary' : 'warning.main' }}
                                  >
                                    <PersonAddOutlinedIcon sx={{ fontSize: 18 }} />
                                  </IconButton>
                                </Tooltip>
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
          </>
        )}

        {/* ── TAB 1: Giám khảo ────────────────────────────────── */}
        {activeTab === 1 && (
          <>
            {loading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}>
                <CircularProgress size={28} thickness={3} />
              </Box>
            ) : examiners.length === 0 ? (
              <Paper variant="outlined" sx={{ p: 5, textAlign: 'center' }}>
                <Typography color="text.secondary">Chưa có dữ liệu giám khảo.</Typography>
              </Paper>
            ) : (
              <Stack spacing={3}>
                {Object.entries(examinersByCenter).map(([centerLabel, list]) => (
                  <Paper key={centerLabel} variant="outlined" sx={{ overflow: 'hidden' }}>
                    <Box sx={{ ...groupHeaderSx, display: 'flex', alignItems: 'center', gap: 1.5 }}>
                      <Typography variant="h6">{centerLabel}</Typography>
                      <Chip label={`${list.length} giám khảo`} size="small" />
                    </Box>

                    <TableContainer>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>Họ tên</TableCell>
                            <TableCell>Email</TableCell>
                            <TableCell>Số điện thoại</TableCell>
                            <TableCell>Chuyên môn</TableCell>
                            <TableCell align="center">Tối đa/ngày</TableCell>
                            <TableCell align="center">Trạng thái</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {list.map((e) => (
                            <TableRow key={e.id} hover>
                              <TableCell>
                                <Stack direction="row" alignItems="center" spacing={1.5}>
                                  <Avatar
                                    sx={{
                                      width: 32,
                                      height: 32,
                                      bgcolor: (theme) => alpha(theme.palette.primary.main, 0.12),
                                      color: 'primary.main',
                                    }}
                                  >
                                    {e.name.charAt(0)}
                                  </Avatar>
                                  <Typography variant="body2" fontWeight={500}>
                                    {e.name}
                                  </Typography>
                                </Stack>
                              </TableCell>
                              <TableCell>
                                <Typography variant="body2" color="text.secondary">
                                  {e.email}
                                </Typography>
                              </TableCell>
                              <TableCell>
                                <Typography variant="body2">{e.phone || '—'}</Typography>
                              </TableCell>
                              <TableCell>
                                <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                                  {e.specialization_names?.map((s) => (
                                    <Chip key={s} label={s} size="small" variant="outlined" />
                                  ))}
                                </Stack>
                              </TableCell>
                              <TableCell align="center">
                                <Chip label={`${e.max_exams_per_day} ca`} size="small" />
                              </TableCell>
                              <TableCell align="center">
                                <Chip
                                  label={e.is_active ? 'Hoạt động' : 'Ngưng'}
                                  size="small"
                                  variant="outlined"
                                  color={e.is_active ? 'success' : 'error'}
                                />
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
          </>
        )}

        {/* ── Assign Examiner Dialog ────────────────────────────── */}
        <Dialog
          open={Boolean(dialogSlot)}
          onClose={() => setDialogSlot(null)}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle sx={{ pb: 1 }}>
            Phân công giám khảo
            {dialogSlot && (
              <Typography variant="body2" color="text.secondary" mt={0.5}>
                {dialogSlot.course_name} — {dialogSlot.exam_date}{' '}
                {dialogSlot.start_time?.substring(0, 5)}
              </Typography>
            )}
          </DialogTitle>

          <DialogContent dividers>
            {suggLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
                <CircularProgress size={24} thickness={3} />
              </Box>
            ) : suggestions.length === 0 ? (
              <Alert severity="warning">Không có giám khảo phù hợp hoặc còn rảnh vào ngày này.</Alert>
            ) : (
              <>
                <Typography variant="body2" color="text.secondary" mb={1.5}>
                  Chọn giám khảo (sắp xếp theo số ca ít nhất):
                </Typography>
                <List dense disablePadding>
                  {suggestions.map((s) => (
                    <ListItemButton
                      key={s.examiner.id}
                      selected={selectedExaminer?.examiner.id === s.examiner.id}
                      onClick={() => setSelectedExaminer(s)}
                      sx={{ mb: 0.5 }}
                    >
                      <ListItemText
                        primary={s.examiner.name}
                        primaryTypographyProps={{ fontWeight: 500, fontSize: '0.875rem' }}
                        secondary={`${s.examiner.specialization_names?.join(', ') || '—'} · Hôm nay: ${s.exams_today}/${s.examiner.max_exams_per_day} ca`}
                        secondaryTypographyProps={{ fontSize: '0.8125rem' }}
                      />
                      {selectedExaminer?.examiner.id === s.examiner.id && (
                        <CheckCircleIcon sx={{ color: 'success.main' }} />
                      )}
                    </ListItemButton>
                  ))}
                </List>
              </>
            )}

            {dialogSlot?.examiner_name && (
              <>
                <Divider sx={{ my: 2 }} />
                <Alert severity="info">
                  Hiện tại: <strong>{dialogSlot.examiner_name}</strong>. Chọn giám khảo khác để thay thế.
                </Alert>
              </>
            )}
          </DialogContent>

          <DialogActions sx={{ px: 3, py: 2 }}>
            <Button onClick={() => setDialogSlot(null)} variant="outlined">
              Huỷ
            </Button>
            <Button
              variant="contained"
              disabled={!selectedExaminer || confirming}
              onClick={handleAssign}
            >
              {confirming ? 'Đang phân công…' : 'Xác nhận'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* ── Add Examiner Dialog ───────────────────────────────── */}
        <AddExaminerDialog
          open={addOpen}
          onClose={() => setAddOpen(false)}
          onCreated={(examiner) => {
            setSuccess(
              examiner?.has_login
                ? `Đã thêm giám khảo ${examiner.name} và tạo tài khoản đăng nhập.`
                : `Đã thêm giám khảo ${examiner?.name || ''}.`
            )
            setActiveTab(1)
            fetchData()
          }}
        />
      </Container>
    </>
  )
}
