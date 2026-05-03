import { useEffect, useRef } from 'react'
import Alert from '@mui/material/Alert'
import Snackbar from '@mui/material/Snackbar'
import { useState } from 'react'
import api from '../api/client'
import useExamStore from '../stores/examStore'

const POLL_INTERVAL_MS = 3000
const TERMINAL_STATUSES = new Set(['SUCCESS', 'COMMITTED', 'FAILURE'])

/**
 * ScheduleTaskPoller — polls GET /api/scheduling/tasks/{taskId} every 3 s
 * while a batch schedule task is in progress.
 *
 * Shows a MUI Snackbar when the task reaches a terminal status:
 *   COMMITTED → success
 *   FAILURE   → error
 *
 * Renders nothing visible while polling.
 */
export default function ScheduleTaskPoller() {
    const taskId = useExamStore((s) => s.scheduleTaskId)
    const setTaskId = useExamStore((s) => s.setScheduleTaskId)

    const [snack, setSnack] = useState({ open: false, severity: 'success', message: '' })
    const intervalRef = useRef(null)

    useEffect(() => {
        if (!taskId) return

        const poll = async () => {
            try {
                const resp = await api.get(`/scheduling/tasks/${taskId}`)
                const data = resp.data
                const status = data?.status

                if (!TERMINAL_STATUSES.has(status)) return  // still pending

                clearInterval(intervalRef.current)
                setTaskId(null)

                if (status === 'COMMITTED' || status === 'SUCCESS') {
                    const count = data?.assigned_count ?? data?.plan?.length ?? '?'
                    setSnack({
                        open: true,
                        severity: 'success',
                        message: `✅ Đã lưu lịch: ${count} giám khảo được gán`,
                    })
                } else if (status === 'FAILURE') {
                    setSnack({
                        open: true,
                        severity: 'error',
                        message: `❌ Lỗi lập lịch: ${data?.error ?? 'Unknown error'}`,
                    })
                }
            } catch {
                // Network error — keep polling silently
            }
        }

        poll()  // immediate first check
        intervalRef.current = setInterval(poll, POLL_INTERVAL_MS)

        return () => clearInterval(intervalRef.current)
    }, [taskId, setTaskId])

    const handleClose = (_event, reason) => {
        if (reason === 'clickaway') return
        setSnack((s) => ({ ...s, open: false }))
    }

    return (
        <Snackbar
            open={snack.open}
            autoHideDuration={6000}
            onClose={handleClose}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        >
            <Alert onClose={handleClose} severity={snack.severity} sx={{ width: '100%' }}>
                {snack.message}
            </Alert>
        </Snackbar>
    )
}
