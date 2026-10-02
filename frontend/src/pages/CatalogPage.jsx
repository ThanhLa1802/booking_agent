import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Box,
  Card,
  CardActionArea,
  CardContent,
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
} from '@mui/material'
import MusicNoteOutlinedIcon from '@mui/icons-material/MusicNoteOutlined'
import CalendarTodayOutlinedIcon from '@mui/icons-material/CalendarTodayOutlined'
import LocationOnOutlinedIcon from '@mui/icons-material/LocationOnOutlined'
import { getSlots } from '../api'
import useExamStore from '../stores/examStore'
import Navbar from '../components/Navbar'

const STYLES = [
  { value: '', label: 'Tất cả loại hình' },
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
      <Container maxWidth="lg" sx={{ py: 5, px: { xs: 2, sm: 3 } }}>
        {/* Header */}
        <Typography variant="h4" mb={1}>Danh mục kỳ thi</Typography>
        <Typography variant="body2" color="text.secondary" mb={4}>
          Chọn kỳ thi phù hợp và bắt đầu đặt lịch với trợ lý AI
        </Typography>

        {/* Filters */}
        <Box sx={{ display: 'flex', gap: 2, mb: 4, flexWrap: 'wrap' }}>
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel>Loại hình</InputLabel>
            <Select
              value={styleFilter}
              label="Loại hình"
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

        {/* States */}
        {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}
        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
            <CircularProgress size={28} />
          </Box>
        )}

        {!loading && slots.length === 0 && (
          <Box className="empty-state">
            <Typography variant="body2">
              Không có lịch thi nào phù hợp với bộ lọc.
            </Typography>
          </Box>
        )}

        {/* Slot grid */}
        <Grid container spacing={2}>
          {slots.map((slot) => (
            <Grid item xs={12} sm={6} md={4} key={slot.id} sx={{ display: 'flex' }}>
              <Card sx={{ width: '100%', display: 'flex' }}>
                <CardActionArea
                  onClick={() => handleBookSlot(slot)}
                  sx={{ height: '100%' }}
                >
                  <CardContent
                    sx={{
                      height: '100%',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 1,
                      p: 2.5,
                    }}
                  >
                    {/* Instrument + Grade */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                      <MusicNoteOutlinedIcon
                        sx={{ color: '#A0825C', fontSize: 20, flexShrink: 0 }}
                      />
                      <Typography variant="h6" noWrap>
                        {slot.instrument_name}
                      </Typography>
                      <Chip
                        label={`Grade ${slot.grade}`}
                        size="small"
                        variant="outlined"
                        sx={{ ml: 'auto', flexShrink: 0 }}
                      />
                    </Box>

                    {/* Style badge */}
                    <Chip
                      label={slot.style_display}
                      size="small"
                      sx={{
                        alignSelf: 'flex-start',
                        fontSize: '0.7rem',
                        bgcolor: '#F0ECE6',
                        color: '#6B5E4F',
                      }}
                    />

                    {/* Date */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                      <CalendarTodayOutlinedIcon
                        sx={{ fontSize: 14, color: 'text.secondary', flexShrink: 0 }}
                      />
                      <Typography variant="body2" color="text.secondary" noWrap>
                        {new Date(slot.exam_date).toLocaleDateString('vi-VN')} — {slot.start_time}
                      </Typography>
                    </Box>

                    {/* Location */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                      <LocationOnOutlinedIcon
                        sx={{ fontSize: 14, color: 'text.secondary', flexShrink: 0 }}
                      />
                      <Typography variant="body2" color="text.secondary" noWrap>
                        {slot.center_name}, {slot.center_city}
                      </Typography>
                    </Box>

                    {/* Footer */}
                    <Box
                      sx={{
                        mt: 'auto',
                        pt: 1,
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                      }}
                    >
                      <Chip
                        size="small"
                        label={
                          slot.available_capacity > 5
                            ? `Còn ${slot.available_capacity} chỗ`
                            : `Còn ${slot.available_capacity} chỗ`
                        }
                        sx={{
                          bgcolor:
                            slot.available_capacity > 5
                              ? 'rgba(92,138,103,0.1)'
                              : 'rgba(196,148,80,0.1)',
                          color:
                            slot.available_capacity > 5
                              ? '#5C8A67'
                              : '#C49450',
                          fontSize: '0.75rem',
                          fontWeight: 500,
                        }}
                      />
                      <Typography
                        variant="body2"
                        fontWeight={600}
                        color="#A0825C"
                      >
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
