import { useEffect, useState } from 'react'
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Checkbox,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { createExaminer, getInstruments } from '../api'

const EMPTY = {
  name: '',
  email: '',
  phone: '',
  specializations: [],
  maxExamsPerDay: 8,
  createLogin: true,
  password: '',
}

function extractError(err) {
  const data = err.response?.data
  if (!data) return 'Không thể thêm giám khảo. Vui lòng thử lại.'
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  const key = Object.keys(data)[0]
  if (!key) return 'Không thể thêm giám khảo. Vui lòng thử lại.'
  const value = Array.isArray(data[key]) ? data[key][0] : data[key]
  return `${key}: ${value}`
}

export default function AddExaminerDialog({ open, onClose, onCreated }) {
  const [form, setForm] = useState(EMPTY)
  const [instruments, setInstruments] = useState([])
  const [loadingInstruments, setLoadingInstruments] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  // Load instrument options once (async setState is safe outside the effect body).
  useEffect(() => {
    let active = true
    getInstruments()
      .then((res) => {
        if (active) setInstruments(res.data || [])
      })
      .catch(() => {
        if (active) setInstruments([])
      })
      .finally(() => {
        if (active) setLoadingInstruments(false)
      })
    return () => {
      active = false
    }
  }, [])

  const close = () => {
    setForm(EMPTY)
    setError(null)
    onClose()
  }

  const setField = (key) => (e) =>
    setForm((f) => ({ ...f, [key]: e.target.value }))

  const selectedInstruments = instruments.filter((i) =>
    form.specializations.includes(i.id)
  )

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)

    if (!form.name.trim() || !form.email.trim()) {
      setError('Vui lòng nhập họ tên và email.')
      return
    }
    if (form.createLogin && form.password.length < 8) {
      setError('Mật khẩu đăng nhập phải có ít nhất 8 ký tự.')
      return
    }

    const payload = {
      name: form.name.trim(),
      email: form.email.trim(),
      phone: form.phone.trim(),
      specializations: form.specializations,
      max_exams_per_day: Number(form.maxExamsPerDay) || 8,
    }
    if (form.createLogin) payload.password = form.password

    setSubmitting(true)
    try {
      const res = await createExaminer(payload)
      onCreated?.(res.data)
      close()
    } catch (err) {
      setError(extractError(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onClose={close} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ pb: 1 }}>Thêm giám khảo</DialogTitle>
      <DialogContent dividers>
        <Typography variant="body2" color="text.secondary" mb={2}>
          Giám khảo sẽ được thêm vào trung tâm của bạn. Nếu đặt mật khẩu, một tài
          khoản đăng nhập (vai trò Giám khảo) sẽ được tạo để họ xem lịch thi của mình.
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Box component="form" id="add-examiner-form" onSubmit={handleSubmit} noValidate>
          <Stack spacing={2}>
            <TextField
              label="Họ tên"
              value={form.name}
              onChange={setField('name')}
              fullWidth
              required
              autoFocus
            />
            <TextField
              label="Email"
              type="email"
              value={form.email}
              onChange={setField('email')}
              fullWidth
              required
            />
            <TextField
              label="Số điện thoại"
              value={form.phone}
              onChange={setField('phone')}
              fullWidth
            />
            <Autocomplete
              multiple
              options={instruments}
              value={selectedInstruments}
              loading={loadingInstruments}
              getOptionLabel={(o) => `${o.name} (${o.style_display})`}
              isOptionEqualToValue={(o, v) => o.id === v.id}
              onChange={(_, value) =>
                setForm((f) => ({ ...f, specializations: value.map((v) => v.id) }))
              }
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Chuyên môn (để trống = dạy mọi nhạc cụ)"
                  placeholder="Chọn nhạc cụ"
                />
              )}
            />
            <TextField
              label="Tối đa ca/ngày"
              type="number"
              value={form.maxExamsPerDay}
              onChange={setField('maxExamsPerDay')}
              inputProps={{ min: 1, max: 30 }}
              fullWidth
            />

            <FormControlLabel
              control={
                <Checkbox
                  checked={form.createLogin}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, createLogin: e.target.checked }))
                  }
                />
              }
              label="Tạo tài khoản đăng nhập cho giám khảo"
            />
            {form.createLogin && (
              <TextField
                label="Mật khẩu"
                type="password"
                value={form.password}
                onChange={setField('password')}
                fullWidth
                required
                autoComplete="new-password"
                helperText="Tối thiểu 8 ký tự. Tên đăng nhập là email ở trên."
              />
            )}
          </Stack>
        </Box>
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={close} variant="outlined" disabled={submitting}>
          Huỷ
        </Button>
        <Button
          type="submit"
          form="add-examiner-form"
          variant="contained"
          disabled={submitting}
        >
          {submitting ? <CircularProgress size={20} sx={{ color: 'inherit' }} /> : 'Thêm'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
