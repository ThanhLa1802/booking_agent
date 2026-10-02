import { useEffect, useRef, useState } from 'react'
import {
  Box,
  Chip,
  Container,
  IconButton,
  InputAdornment,
  TextField,
  Typography,
} from '@mui/material'
import SendIcon from '@mui/icons-material/Send'
import MusicNoteOutlinedIcon from '@mui/icons-material/MusicNoteOutlined'
import useAuthStore from '../stores/authStore'
import useChatStore from '../stores/chatStore'
import useExamStore from '../stores/examStore'
import { createChatStream } from '../api'
import ChatBubble from '../components/ChatBubble'
import ConfirmBanner from '../components/ConfirmBanner'
import Navbar from '../components/Navbar'

const CONFIRM_SIGNAL = 'xác nhận'
const CANCEL_SIGNAL = 'hủy bỏ thao tác'

export default function ChatPage() {
  const { accessToken } = useAuthStore()
  const {
    messages, streaming, streamingContent, activeTools, pendingConfirm, sessionId,
    addUserMessage, startStreaming, appendToken, addToolCall, removeToolCall,
    finishStreaming, setError, setSessionId, clearPendingConfirm, setStreamingContent,
  } = useChatStore()
  const { selectedSlot, reset: resetExam } = useExamStore()

  const [input, setInput] = useState('')
  const bottomRef = useRef(null)
  const abortRef = useRef(null)

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  // Pre-fill if slot was selected from catalog. Syncing an external store
  // selection into the editable draft is intentional here.
  useEffect(() => {
    if (selectedSlot) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setInput(
        `Tôi muốn đặt lịch thi slot ${selectedSlot.id} — ${selectedSlot.instrument_name} Grade ${selectedSlot.grade} vào ngày ${new Date(selectedSlot.exam_date).toLocaleDateString('vi-VN')}`
      )
    }
  }, [selectedSlot])

  const sendMessage = async (text) => {
    if (!text.trim() || streaming) return
    const msg = text.trim()
    setInput('')
    addUserMessage(msg)
    startStreaming()

    const sid = sessionId || crypto.randomUUID()
    if (!sessionId) setSessionId(sid)

    try {
      const response = await createChatStream(msg, sid, accessToken)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      abortRef.current = reader
      let buffer = ''
      let hasPendingConfirm = false
      let doneContent = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (!raw || raw === '[DONE]') continue
          try {
            const event = JSON.parse(raw)
            if (event.type === 'token') {
              appendToken(event.content)
              if (
                event.content.includes('Confirmation required') ||
                event.content.includes('⚠️')
              ) {
                hasPendingConfirm = true
              }
            } else if (event.type === 'tool_start') {
              addToolCall(event.tool)
            } else if (event.type === 'tool_end') {
              removeToolCall(event.tool)
            } else if (event.type === 'done') {
              doneContent = event.content || ''
              break
            } else if (event.type === 'error') {
              setError(event.content)
              return
            }
          } catch {
            // ignore parse errors
          }
        }
      }

      if (doneContent) {
        setStreamingContent(doneContent)
      }
      finishStreaming(hasPendingConfirm)
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message || 'Lỗi kết nối. Vui lòng thử lại.')
      }
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    resetExam()
    sendMessage(input)
  }

  const handleConfirm = () => {
    clearPendingConfirm()
    sendMessage(CONFIRM_SIGNAL)
  }

  const handleCancel = () => {
    clearPendingConfirm()
    sendMessage(CANCEL_SIGNAL)
  }

  const hasContent = messages.length > 0

  return (
    <>
      <Navbar />
      <Container
        maxWidth="md"
        disableGutters
        sx={{
          display: 'flex',
          flexDirection: 'column',
          height: 'calc(100svh - 56px)',
          px: { xs: 2, sm: 3 },
        }}
      >
        {/* ── Header: staff line + title ────────────────────────── */}
        <Box sx={{ pt: 3, pb: 2, flexShrink: 0 }}>
          {/* Hairline rule — the single staff line */}
          <Box
            className={`staff-line${hasContent ? '' : ' enter'}`}
            sx={{ mb: 2 }}
          />

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <MusicNoteOutlinedIcon
              sx={{
                color: streaming ? '#A0825C' : '#C4AC84',
                fontSize: 18,
                transition: 'color 0.6s ease',
              }}
            />
            <Typography
              variant="body2"
              color="text.secondary"
              fontWeight={400}
              letterSpacing="-0.005em"
            >
              {streaming
                ? 'Đang trả lời...'
                : 'Trợ lý tư vấn thi Trinity'}
            </Typography>
          </Box>
        </Box>

        {/* ── Messages ──────────────────────────────────────────── */}
        <Box sx={{ flex: 1, overflowY: 'auto', py: 1 }}>
          {!hasContent && !streaming && (
            <Box className="empty-state" sx={{ mt: 6 }}>
              <Typography variant="body1" color="text.secondary" mb={1}>
                Xin chào!
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Tôi có thể giúp bạn tra cứu chương trình thi,<br />
                tư vấn cấp độ, và đặt lịch thi Trinity.
              </Typography>
            </Box>
          )}

          {messages.map((msg, i) => (
            <ChatBubble key={i} role={msg.role} content={msg.content} />
          ))}

          {streaming && streamingContent && (
            <ChatBubble
              role="assistant"
              content={streamingContent}
              streaming
            />
          )}

          {/* Tool call chips */}
          {streaming && activeTools.length > 0 && !streamingContent && (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                px: 0.5,
                mb: 2,
                pl: 6,
              }}
            >
              {activeTools.map((tool) => (
                <Chip
                  key={tool}
                  label={tool.replace(/_/g, ' ')}
                  size="small"
                  variant="outlined"
                  sx={{
                    fontSize: '0.75rem',
                    color: 'text.secondary',
                    borderColor: 'divider',
                  }}
                />
              ))}
            </Box>
          )}

          <div ref={bottomRef} />
        </Box>

        {/* ── Confirmation banner ────────────────────────────────── */}
        {pendingConfirm && (
          <ConfirmBanner onConfirm={handleConfirm} onCancel={handleCancel} />
        )}

        {/* ── Input ─────────────────────────────────────────────── */}
        <Box className="chat-input-container" sx={{ flexShrink: 0 }}>
          <Box
            component="form"
            onSubmit={handleSubmit}
            sx={{ display: 'flex', alignItems: 'flex-end', gap: 1 }}
          >
            <TextField
              fullWidth
              size="small"
              placeholder="Nhập câu hỏi hoặc yêu cầu..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={streaming}
              multiline
              maxRows={4}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSubmit(e)
                }
              }}
              sx={{
                '& .MuiOutlinedInput-root': {
                  backgroundColor: '#F5F4F2',
                  borderRadius: '12px',
                  fontSize: '0.9375rem',
                },
              }}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      type="submit"
                      disabled={!input.trim() || streaming}
                      size="small"
                      sx={{
                        color: input.trim() && !streaming ? '#A0825C' : '#CCC8C2',
                        transition: 'color 0.2s ease',
                      }}
                    >
                      <SendIcon sx={{ fontSize: 18 }} />
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
          </Box>
        </Box>
      </Container>
    </>
  )
}
