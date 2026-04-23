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
import { getSlots } from '../api'
import useExamStore from '../stores/examStore'
import Navbar from '../components/Navbar'

const STYLES = [
    { value: '', label: 'All' },
    { value: 'CLASSICAL_JAZZ', label: 'Classical & Jazz' },
    { value: 'ROCK_POP', label: 'Rock & Pop' },
    { value: 'THEORY', label: 'Music Theory' },
]

export default function CatalogPage() {
    const navigate = useNavigate()
    const {
        slots, selectSlot,
        setSlots, loading, error, setLoading, setError,
    } = useExamStore()

    const [styleFilter, setStyleFilter] = useState('')
    const [gradeFilter, setGradeFilter] = useState('')

    useEffect(() => {
        const fetchData = async () => {
            setLoading(true)
            try {
                const params = {}
                if (styleFilter) params.style = styleFilter
                if (gradeFilter) params.grade = gradeFilter
                const slotsRes = await getSlots(params)
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
                    Exam Catalog
                </Typography>

                {/* Filters */}
                <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
                    <FormControl size="small" sx={{ minWidth: 200 }}>
                        <InputLabel>Exam Type</InputLabel>
                        <Select
                            value={styleFilter}
                            label="Exam Type"
                            onChange={(e) => setStyleFilter(e.target.value)}
                        >
                            {STYLES.map((s) => (
                                <MenuItem key={s.value} value={s.value}>{s.label}</MenuItem>
                            ))}
                        </Select>
                    </FormControl>
                    <FormControl size="small" sx={{ minWidth: 120 }}>
                        <InputLabel>Grade</InputLabel>
                        <Select
                            value={gradeFilter}
                            label="Grade"
                            onChange={(e) => setGradeFilter(e.target.value)}
                        >
                            <MenuItem value="">All</MenuItem>
                            {[1, 2, 3, 4, 5, 6, 7, 8].map((g) => (
                                <MenuItem key={g} value={g}>Grade {g}</MenuItem>
                            ))}
                        </Select>
                    </FormControl>
                </Box>

                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                {loading && <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}><CircularProgress /></Box>}

                {!loading && slots.length === 0 && (
                    <Typography color="text.secondary">No available slots.</Typography>
                )}

                <Grid container spacing={2}>
                    {slots.map((slot) => (
                        <Grid item xs={12} sm={6} md={4} key={slot.id} sx={{ display: 'flex' }}>
                            <Card
                                variant="outlined"
                                sx={{ width: '100%', height: 230, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
                            >
                                <CardActionArea
                                    onClick={() => handleBookSlot(slot)}
                                    sx={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'stretch', justifyContent: 'flex-start' }}
                                >
                                    <CardContent sx={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', gap: 0.75, overflow: 'hidden', boxSizing: 'border-box' }}>
                                        {/* Header: instrument + grade */}
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, overflow: 'hidden' }}>
                                            <MusicNoteIcon color="primary" fontSize="small" sx={{ flexShrink: 0 }} />
                                            <Typography
                                                variant="subtitle1"
                                                fontWeight={600}
                                                noWrap
                                                sx={{ overflow: 'hidden', textOverflow: 'ellipsis' }}
                                                title={`${slot.instrument_name} — Grade ${slot.grade}`}
                                            >
                                                {slot.instrument_name} — Grade {slot.grade}
                                            </Typography>
                                        </Box>

                                        {/* Style badge */}
                                        <Chip
                                            size="small"
                                            label={slot.style_display}
                                            variant="outlined"
                                            color="primary"
                                            sx={{ alignSelf: 'flex-start', fontSize: '0.7rem', flexShrink: 0 }}
                                        />

                                        {/* Date + time */}
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, overflow: 'hidden' }}>
                                            <EventAvailableIcon fontSize="small" color="success" sx={{ flexShrink: 0 }} />
                                            <Typography variant="body2" noWrap sx={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                                {new Date(slot.exam_date).toLocaleDateString('vi-VN')} — {slot.start_time}
                                            </Typography>
                                        </Box>

                                        {/* Location */}
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, overflow: 'hidden' }}>
                                            <Typography variant="body2" color="text.secondary" noWrap
                                                sx={{ overflow: 'hidden', textOverflow: 'ellipsis' }}
                                                title={`${slot.center_name}, ${slot.center_city}`}
                                            >
                                                📍 {slot.center_name}, {slot.center_city}
                                            </Typography>
                                        </Box>

                                        {/* Footer: capacity + fee */}
                                        <Box sx={{ mt: 'auto', pt: 0.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
                                            <Chip
                                                size="small"
                                                color={slot.available_capacity > 5 ? 'success' : 'warning'}
                                                label={`Remaining ${slot.available_capacity} slots`}
                                            />
                                            <Typography variant="body2" fontWeight={700} color="primary.main">
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
