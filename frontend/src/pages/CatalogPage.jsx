import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    Box,
    Card,
    CardContent,
    CardActionArea,
    Chip,
    CircularProgress,
    Container,
    FormControl,
    Grid,
    InputLabel,
    MenuItem,
    Select,
    Typography,
    Alert,
    Button,
} from '@mui/material'
import MusicNoteIcon from '@mui/icons-material/MusicNote'
import EventAvailableIcon from '@mui/icons-material/EventAvailable'
import { getCourses, getSlots } from '../api'
import useExamStore from '../stores/examStore'
import Navbar from '../components/Navbar'

const STYLES = [
    { value: '', label: 'Tất cả' },
    { value: 'classical_jazz', label: 'Classical & Jazz' },
    { value: 'rock_pop', label: 'Rock & Pop' },
    { value: 'theory', label: 'Lý thuyết âm nhạc' },
]

export default function CatalogPage() {
    const navigate = useNavigate()
    const {
        instruments, grades, slots, selectedStyle,
        setInstruments, setGrades, setSlots,
        selectStyle, selectSlot, loading, error, setLoading, setError,
    } = useExamStore()

    const [styleFilter, setStyleFilter] = useState('')
    const [gradeFilter, setGradeFilter] = useState('')

    useEffect(() => {
        const fetchData = async () => {
            setLoading(true)
            try {
                const params = {}
                if (styleFilter) params.exam_type = styleFilter
                if (gradeFilter) params.grade = gradeFilter
                const [coursesRes, slotsRes] = await Promise.all([
                    getCourses(params),
                    getSlots({ available_only: true, ...params }),
                ])
                setInstruments(coursesRes.data.instruments || [])
                setGrades(coursesRes.data.grades || [])
                setSlots(slotsRes.data || [])
            } catch (err) {
                setError(err.response?.data?.detail || 'Không thể tải dữ liệu.')
            } finally {
                setLoading(false)
            }
        }
        fetchData()
    }, [styleFilter, gradeFilter])

    const handleBookSlot = (slot) => {
        selectSlot(slot)
        navigate('/chat')
    }

    return (
        <>
            <Navbar />
            <Container maxWidth="lg" sx={{ py: 4 }}>
                <Typography variant="h5" fontWeight={700} gutterBottom>
                    Danh mục kỳ thi
                </Typography>

                {/* Filters */}
                <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
                    <FormControl size="small" sx={{ minWidth: 200 }}>
                        <InputLabel>Loại hình thi</InputLabel>
                        <Select
                            value={styleFilter}
                            label="Loại hình thi"
                            onChange={(e) => setStyleFilter(e.target.value)}
                        >
                            {STYLES.map((s) => (
                                <MenuItem key={s.value} value={s.value}>{s.label}</MenuItem>
                            ))}
                        </Select>
                    </FormControl>
                    <FormControl size="small" sx={{ minWidth: 120 }}>
                        <InputLabel>Cấp độ</InputLabel>
                        <Select
                            value={gradeFilter}
                            label="Cấp độ"
                            onChange={(e) => setGradeFilter(e.target.value)}
                        >
                            <MenuItem value="">Tất cả</MenuItem>
                            {[1, 2, 3, 4, 5, 6, 7, 8].map((g) => (
                                <MenuItem key={g} value={g}>Grade {g}</MenuItem>
                            ))}
                        </Select>
                    </FormControl>
                </Box>

                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                {loading && <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}><CircularProgress /></Box>}

                {!loading && slots.length === 0 && (
                    <Typography color="text.secondary">Không có slot nào khả dụng.</Typography>
                )}

                <Grid container spacing={2}>
                    {slots.map((slot) => (
                        <Grid item xs={12} sm={6} md={4} key={slot.id}>
                            <Card variant="outlined">
                                <CardActionArea onClick={() => handleBookSlot(slot)}>
                                    <CardContent>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                            <MusicNoteIcon color="primary" fontSize="small" />
                                            <Typography variant="subtitle1" fontWeight={600}>
                                                {slot.instrument} — Grade {slot.grade}
                                            </Typography>
                                        </Box>
                                        <Typography variant="body2" color="text.secondary" gutterBottom>
                                            {slot.exam_type_display || slot.exam_type}
                                        </Typography>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
                                            <EventAvailableIcon fontSize="small" color="success" />
                                            <Typography variant="body2">
                                                {new Date(slot.exam_date).toLocaleDateString('vi-VN')} — {slot.start_time}
                                            </Typography>
                                        </Box>
                                        <Box sx={{ mt: 1.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                            <Chip
                                                size="small"
                                                color={slot.available_capacity > 5 ? 'success' : 'warning'}
                                                label={`Còn ${slot.available_capacity} chỗ`}
                                            />
                                            <Typography variant="body2" fontWeight={600}>
                                                {Number(slot.fee).toLocaleString('vi-VN')}đ
                                            </Typography>
                                        </Box>
                                    </CardContent>
                                </CardActionArea>
                            </Card>
                        </Grid>
                    ))}
                </Grid>
            </Container>
        </>
    )
}
