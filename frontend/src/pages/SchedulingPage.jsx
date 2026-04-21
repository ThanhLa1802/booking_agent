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
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth'
import PeopleAltIcon from '@mui/icons-material/PeopleAlt'
import PersonAddIcon from '@mui/icons-material/PersonAdd'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import LocationOnIcon from '@mui/icons-material/LocationOn'
import RefreshIcon from '@mui/icons-material/Refresh'
import Navbar from '../components/Navbar'
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

    // assign dialog state
    const [dialogSlot, setDialogSlot] = useState(null)
    const [suggestions, setSuggestions] = useState([])
    const [suggLoading, setSuggLoading] = useState(false)
    const [selectedExaminer, setSelectedExaminer] = useState(null)
    const [confirming, setConfirming] = useState(false)

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
            setSuccess(`Đã gán ${selectedExaminer.examiner.name} vào slot ${dialogSlot.id}`)
            setDialogSlot(null)
            fetchData()
        } catch (err) {
            setError(err.response?.data?.detail || 'Gán examiner thất bại.')
            setDialogSlot(null)
        } finally {
            setConfirming(false)
        }
    }

    // Group slots by date for display
    const grouped = slots.reduce((acc, s) => {
        const key = s.exam_date
        if (!acc[key]) acc[key] = []
        acc[key].push(s)
        return acc
    }, {})

    const sortedDates = Object.keys(grouped).sort()

    // Group examiners by center for the examiner tab
    const examinersByCenter = examiners.reduce((acc, e) => {
        const key = `${e.center_name} — ${e.center_city}`
        if (!acc[key]) acc[key] = []
        acc[key].push(e)
        return acc
    }, {})

    return (
        <>
            <Navbar />
            <Container maxWidth="xl" sx={{ py: 5, px: { xs: 2, md: 4 } }}>
                {/* Header */}
                <Stack direction="row" alignItems="center" spacing={2} mb={3}>
                    <CalendarMonthIcon color="primary" sx={{ fontSize: 40 }} />
                    <Box flexGrow={1}>
                        <Typography variant="h4" fontWeight={700}>
                            Quản lý lịch thi
                        </Typography>
                        <Typography variant="body1" color="text.secondary" mt={0.5}>
                            Phân công giám khảo cho các ca thi
                        </Typography>
                    </Box>
                    <Tooltip title="Làm mới">
                        <IconButton onClick={fetchData} disabled={loading} size="large">
                            <RefreshIcon />
                        </IconButton>
                    </Tooltip>
                </Stack>

                {/* Navigation Tabs */}
                <Paper variant="outlined" sx={{ mb: 3 }}>
                    <Tabs
                        value={activeTab}
                        onChange={(_, v) => setActiveTab(v)}
                        indicatorColor="primary"
                        textColor="primary"
                    >
                        <Tab
                            icon={<CalendarMonthIcon fontSize="small" />}
                            iconPosition="start"
                            label="Lịch thi"
                            sx={{ minHeight: 52 }}
                        />
                        <Tab
                            icon={<PeopleAltIcon fontSize="small" />}
                            iconPosition="start"
                            label={`Giám khảo${examiners.length ? ` (${examiners.length})` : ''}`}
                            sx={{ minHeight: 52 }}
                        />
                    </Tabs>
                </Paper>

                {/* Alerts */}
                {error && <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>{error}</Alert>}
                {success && <Alert severity="success" onClose={() => setSuccess(null)} sx={{ mb: 2 }}>{success}</Alert>}

                {/* ── TAB 0: Lịch thi ── */}
                {activeTab === 0 && (
                    <>
                        {/* Date range filter */}
                        <Paper variant="outlined" sx={{ p: 3, mb: 4 }}>
                            <Stack direction="row" spacing={3} flexWrap="wrap" alignItems="center">
                                <TextField
                                    label="Từ ngày"
                                    type="date"
                                    size="small"
                                    value={dateFrom}
                                    onChange={(e) => setDateFrom(e.target.value)}
                                    InputLabelProps={{ shrink: true }}
                                    sx={{ minWidth: 180 }}
                                />
                                <TextField
                                    label="Đến ngày"
                                    type="date"
                                    size="small"
                                    value={dateTo}
                                    onChange={(e) => setDateTo(e.target.value)}
                                    InputLabelProps={{ shrink: true }}
                                    sx={{ minWidth: 180 }}
                                />
                                <Button variant="contained" onClick={fetchData} disabled={loading} sx={{ px: 4 }}>
                                    Tìm kiếm
                                </Button>
                            </Stack>
                        </Paper>

                        {/* Alerts */}
                        {error && <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>{error}</Alert>}
                        {success && <Alert severity="success" onClose={() => setSuccess(null)} sx={{ mb: 2 }}>{success}</Alert>}

                        {/* Stats row */}
                        {!loading && slots.length > 0 && (
                            <Stack direction="row" spacing={2} mb={4} flexWrap="wrap">
                                <Chip
                                    label={`${slots.length} ca thi`}
                                    color="primary"
                                    variant="filled"
                                    sx={{ px: 1, fontSize: '0.875rem' }}
                                />
                                <Chip
                                    label={`${slots.filter(s => s.examiner_id).length} đã phân công`}
                                    color="success"
                                    variant="filled"
                                    sx={{ px: 1, fontSize: '0.875rem' }}
                                />
                                <Chip
                                    label={`${slots.filter(s => !s.examiner_id).length} chưa phân công`}
                                    color="warning"
                                    variant="filled"
                                    sx={{ px: 1, fontSize: '0.875rem' }}
                                />
                            </Stack>
                        )}

                        {loading ? (
                            <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
                                <CircularProgress />
                            </Box>
                        ) : slots.length === 0 ? (
                            <Paper sx={{ p: 4, textAlign: 'center' }}>
                                <Typography color="text.secondary">
                                    Không có ca thi nào trong khoảng thời gian này.
                                </Typography>
                            </Paper>
                        ) : (
                            /* Calendar table grouped by date */
                            <Stack spacing={4}>
                                {sortedDates.map((date) => (
                                    <Paper key={date} elevation={1}>
                                        <Box
                                            sx={{
                                                px: 2, py: 1,
                                                bgcolor: 'primary.main',
                                                borderRadius: '4px 4px 0 0',
                                            }}
                                        >
                                            <Typography color="white" fontWeight={600}>
                                                {new Date(date + 'T00:00:00').toLocaleDateString('vi-VN', {
                                                    weekday: 'long', year: 'numeric',
                                                    month: 'long', day: 'numeric',
                                                })}
                                            </Typography>
                                        </Box>
                                        <TableContainer>
                                            <Table size="medium">
                                                <TableHead>
                                                    <TableRow sx={{ bgcolor: 'grey.50' }}>
                                                        <TableCell>Giờ</TableCell>
                                                        <TableCell>Ca thi</TableCell>
                                                        <TableCell>Trung tâm</TableCell>
                                                        <TableCell>Loại</TableCell>
                                                        <TableCell align="center">Đặt / Tổng</TableCell>
                                                        <TableCell>Giám khảo</TableCell>
                                                        <TableCell align="center">Thao tác</TableCell>
                                                    </TableRow>
                                                </TableHead>
                                                <TableBody>
                                                    {grouped[date].map((slot) => (
                                                        <TableRow
                                                            key={slot.id}
                                                            hover
                                                            sx={{
                                                                bgcolor: !slot.examiner_id
                                                                    ? 'warning.50'
                                                                    : 'inherit',
                                                            }}
                                                        >
                                                            <TableCell sx={{ whiteSpace: 'nowrap' }}>
                                                                {slot.start_time?.substring(0, 5)}
                                                            </TableCell>
                                                            <TableCell>
                                                                <Typography variant="body2" fontWeight={500}>
                                                                    {slot.course_name}
                                                                </Typography>
                                                            </TableCell>
                                                            <TableCell>
                                                                <Typography variant="body2">
                                                                    {slot.center_name}
                                                                </Typography>
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
                                                                <Typography variant="body2">
                                                                    {slot.capacity - slot.available_capacity}/{slot.capacity}
                                                                </Typography>
                                                            </TableCell>
                                                            <TableCell>
                                                                {slot.examiner_name ? (
                                                                    <Stack direction="row" alignItems="center" spacing={0.5}>
                                                                        <CheckCircleIcon
                                                                            fontSize="small"
                                                                            color="success"
                                                                        />
                                                                        <Typography variant="body2">
                                                                            {slot.examiner_name}
                                                                        </Typography>
                                                                    </Stack>
                                                                ) : (
                                                                    <Typography
                                                                        variant="body2"
                                                                        color="warning.main"
                                                                        fontStyle="italic"
                                                                    >
                                                                        Chưa phân công
                                                                    </Typography>
                                                                )}
                                                            </TableCell>
                                                            <TableCell align="center">
                                                                <Tooltip title="Phân công giám khảo">
                                                                    <IconButton
                                                                        size="small"
                                                                        color={slot.examiner_id ? 'default' : 'warning'}
                                                                        onClick={() => handleOpenAssign(slot)}
                                                                    >
                                                                        <PersonAddIcon fontSize="small" />
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

                        {/* Examiner sidebar summary — removed (now in Tab 1) */}
                    </> /* end Tab 0 */
                )}

                {/* ── TAB 1: Giám khảo ── */}
                {activeTab === 1 && (
                    <>
                        {loading ? (
                            <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
                                <CircularProgress />
                            </Box>
                        ) : examiners.length === 0 ? (
                            <Paper sx={{ p: 4, textAlign: 'center' }}>
                                <Typography color="text.secondary">Chưa có dữ liệu giám khảo.</Typography>
                            </Paper>
                        ) : (
                            <Stack spacing={4}>
                                {Object.entries(examinersByCenter).map(([centerLabel, list]) => (
                                    <Paper key={centerLabel} elevation={1}>
                                        {/* Center header */}
                                        <Box sx={{
                                            px: 3, py: 1.5,
                                            bgcolor: 'secondary.main',
                                            borderRadius: '4px 4px 0 0',
                                            display: 'flex', alignItems: 'center', gap: 1,
                                        }}>
                                            <LocationOnIcon sx={{ color: 'white', fontSize: 20 }} />
                                            <Typography color="white" fontWeight={600} variant="subtitle1">
                                                {centerLabel}
                                            </Typography>
                                            <Chip
                                                label={`${list.length} giám khảo`}
                                                size="small"
                                                sx={{ ml: 1, bgcolor: 'rgba(255,255,255,0.25)', color: 'white', fontWeight: 600 }}
                                            />
                                        </Box>
                                        <TableContainer>
                                            <Table size="medium">
                                                <TableHead>
                                                    <TableRow sx={{ bgcolor: 'grey.50' }}>
                                                        <TableCell>Họ tên</TableCell>
                                                        <TableCell>Email</TableCell>
                                                        <TableCell>Số điện thoại</TableCell>
                                                        <TableCell>Chuyên môn</TableCell>
                                                        <TableCell align="center">Tối đa / ngày</TableCell>
                                                        <TableCell align="center">Trạng thái</TableCell>
                                                    </TableRow>
                                                </TableHead>
                                                <TableBody>
                                                    {list.map((e) => (
                                                        <TableRow key={e.id} hover>
                                                            <TableCell>
                                                                <Stack direction="row" alignItems="center" spacing={1.5}>
                                                                    <Avatar sx={{ width: 36, height: 36, bgcolor: 'primary.light', fontSize: 14 }}>
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
                                                                <Chip
                                                                    label={`${e.max_exams_per_day} ca`}
                                                                    size="small"
                                                                    color="primary"
                                                                    variant="outlined"
                                                                />
                                                            </TableCell>
                                                            <TableCell align="center">
                                                                <Chip
                                                                    label={e.is_active ? 'Hoạt động' : 'Ngưng'}
                                                                    size="small"
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
                    </> /* end Tab 1 */
                )}

                {/* Assign Examiner Dialog */}
                <Dialog
                    open={Boolean(dialogSlot)}
                    onClose={() => setDialogSlot(null)}
                    maxWidth="sm"
                    fullWidth
                >
                    <DialogTitle>
                        Phân công giám khảo
                        {dialogSlot && (
                            <Typography variant="body2" color="text.secondary">
                                {dialogSlot.course_name} — {dialogSlot.exam_date} {dialogSlot.start_time?.substring(0, 5)}
                            </Typography>
                        )}
                    </DialogTitle>
                    <DialogContent dividers>
                        {suggLoading ? (
                            <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
                                <CircularProgress size={28} />
                            </Box>
                        ) : suggestions.length === 0 ? (
                            <Alert severity="warning">
                                Không có giám khảo phù hợp hoặc còn rảnh vào ngày này.
                            </Alert>
                        ) : (
                            <>
                                <Typography variant="body2" color="text.secondary" mb={1}>
                                    Chọn giám khảo (sắp xếp theo số ca ít nhất):
                                </Typography>
                                <List dense disablePadding>
                                    {suggestions.map((s) => (
                                        <ListItemButton
                                            key={s.examiner.id}
                                            selected={selectedExaminer?.examiner.id === s.examiner.id}
                                            onClick={() => setSelectedExaminer(s)}
                                            sx={{ borderRadius: 1, mb: 0.5 }}
                                        >
                                            <ListItemText
                                                primary={s.examiner.name}
                                                secondary={
                                                    `${s.examiner.specialization_names?.join(', ') || '—'} | ` +
                                                    `Hôm nay: ${s.exams_today}/${s.examiner.max_exams_per_day} ca`
                                                }
                                            />
                                            {selectedExaminer?.examiner.id === s.examiner.id && (
                                                <CheckCircleIcon color="success" />
                                            )}
                                        </ListItemButton>
                                    ))}
                                </List>
                            </>
                        )}
                        {dialogSlot?.examiner_name && (
                            <>
                                <Divider sx={{ my: 2 }} />
                                <Alert severity="info" sx={{ mt: 1 }}>
                                    Hiện tại: <strong>{dialogSlot.examiner_name}</strong>. Chọn giám khảo khác để thay thế.
                                </Alert>
                            </>
                        )}
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setDialogSlot(null)}>Huỷ</Button>
                        <Button
                            variant="contained"
                            disabled={!selectedExaminer || confirming}
                            onClick={handleAssign}
                            startIcon={confirming ? <CircularProgress size={16} /> : <PersonAddIcon />}
                        >
                            {confirming ? 'Đang gán...' : 'Xác nhận gán'}
                        </Button>
                    </DialogActions>
                </Dialog>
            </Container>
        </>
    )
}
