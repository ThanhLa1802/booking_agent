import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  Box,
  Card,
  CardActionArea,
  CardContent,
  Chip,
  CircularProgress,
  Container,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Typography,
} from '@mui/material'
import MusicNoteOutlinedIcon from '@mui/icons-material/MusicNoteOutlined'
import CalendarTodayOutlinedIcon from '@mui/icons-material/CalendarTodayOutlined'
import LocationOnOutlinedIcon from '@mui/icons-material/LocationOnOutlined'
import ArrowForwardIcon from '@mui/icons-material/ArrowForward'
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
      <Container maxWidth="lg" sx={{ py: { xs: 4, md: 6 }, px: { xs: 2, sm: 3 } }}>
        {/* Header */}
        <Box sx={{ mb: 4 }}>
          <Typography variant="overline" color="primary.main">
            Danh mục
          </Typography>
          <Typography variant="h2" sx={{ mb: 1 }}>
            Kỳ thi âm nhạc
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ maxWidth: 560 }}>
            Chọn kỳ thi phù hợp và bắt đầu đặt lịch với trợ lý AI.
          </Typography>
        </Box>

        {/* Filters */}
        <Box
          sx={{
            display: 'flex',
            gap: 2,
            mb: 4,
            pb: 3,
            flexWrap: 'wrap',
            borderBottom: '1px solid',
            borderColor: 'divider',
          }}
        >
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
          <FormControl size="small" sx={{ minWidth: 130 }}>
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
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}>
            <CircularProgress size={28} thickness={3} />
          </Box>
        )}

        {!loading && slots.length === 0 && (
          <Box sx={{ textAlign: 'center', py: 10, color: 'text.secondary' }}>
            <Typography variant="body1" sx={{ mb: 0.5 }}>
              Không có lịch thi nào phù hợp với bộ lọc.
            </Typography>
            <Typography variant="body2">
              Hãy thử đổi loại hình hoặc cấp độ.
            </Typography>
          </Box>
        )}

        {/* Slot grid */}
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: {
              xs: '1fr',
              sm: 'repeat(2, 1fr)',
              md: 'repeat(3, 1fr)',
            },
            gap: 2.5,
          }}
        >
          {slots.map((slot) => {
            const scarce = slot.available_capacity <= 5
            return (
              <Card key={slot.id} sx={{ display: 'flex' }}>
                <CardActionArea
                  onClick={() => handleBookSlot(slot)}
                  sx={{ height: '100%' }}
                >
                  <CardContent
                    sx={{
                      height: '100%',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 1.25,
                      p: 2.5,
                    }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                      <MusicNoteOutlinedIcon sx={{ color: 'primary.main', fontSize: 20, mt: 0.25 }} />
                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Typography variant="h5" noWrap>
                          {slot.instrument_name}
                        </Typography>
                        <Typography variant="overline" color="text.secondary">
                          {slot.style_display}
                        </Typography>
                      </Box>
                      <Chip label={`Grade ${slot.grade}`} size="small" variant="outlined" />
                    </Box>

                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                      <CalendarTodayOutlinedIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
                      <Typography variant="body2" color="text.secondary" noWrap>
                        {new Date(slot.exam_date).toLocaleDateString('vi-VN')} — {slot.start_time}
                      </Typography>
                    </Box>

                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                      <LocationOnOutlinedIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
                      <Typography variant="body2" color="text.secondary" noWrap>
                        {slot.center_name}, {slot.center_city}
                      </Typography>
                    </Box>

                    {/* Footer */}
                    <Box
                      sx={{
                        mt: 'auto',
                        pt: 1.5,
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        borderTop: '1px solid',
                        borderColor: 'divider',
                      }}
                    >
                      <Chip
                        size="small"
                        label={`Còn ${slot.available_capacity} chỗ`}
                        color={scarce ? 'warning' : 'success'}
                        variant="outlined"
                        sx={{ fontWeight: 500 }}
                      />
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <Typography variant="body2" fontWeight={600} color="primary.main">
                          {Number(slot.fee).toLocaleString('vi-VN')}đ
                        </Typography>
                        <ArrowForwardIcon sx={{ fontSize: 16, color: 'text.disabled' }} />
                      </Box>
                    </Box>
                  </CardContent>
                </CardActionArea>
              </Card>
            )
          })}
        </Box>
      </Container>
    </>
  )
}
