import { useEffect, useRef, useState } from 'react'
import {
    Box,
    Container,
    IconButton,
    InputAdornment,
    Paper,
    TextField,
    Typography,
} from '@mui/material'
import SendIcon from '@mui/icons-material/Send'
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
        messages, streaming, streamingContent, pendingConfirm, sessionId,
        addUserMessage, startStreaming, appendToken, addToolCall,
        finishStreaming, setError, setSessionId, clearPendingConfirm,
    } = useChatStore()
    const { selectedSlot, reset: resetExam } = useExamStore()

    const [input, setInput] = useState('')
    const bottomRef = useRef(null)
    const abortRef = useRef(null)

    // Auto-scroll
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages, streamingContent])

    // Pre-fill message if a slot was selected in catalog
    useEffect(() => {
        if (selectedSlot) {
            setInput(
                `Tôi muốn đặt lịch thi slot ${selectedSlot.id} — ${selectedSlot.instrument} Grade ${selectedSlot.grade} vào ngày ${new Date(selectedSlot.exam_date).toLocaleDateString('vi-VN')}`
            )
            resetExam()
        }
    }, [selectedSlot])

    const sendMessage = async (text) => {
        if (!text.trim() || streaming) return
        const msg = text.trim()
        setInput('')
        addUserMessage(msg)
        startStreaming()

        // Generate session ID if first message
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

            while (true) {
                const { done, value } = await reader.read()
                if (done) break
                buffer += decoder.decode(value, { stream: true })

                // Parse SSE lines
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
                            if (event.content.includes('Confirmation required') || event.content.includes('⚠️')) {
                                hasPendingConfirm = true
                            }
                        } else if (event.type === 'tool_start') {
                            addToolCall(event.tool)
                        } else if (event.type === 'done') {
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

            finishStreaming(hasPendingConfirm)
        } catch (err) {
            if (err.name !== 'AbortError') {
                setError(err.message || 'Lỗi kết nối. Vui lòng thử lại.')
            }
        }
    }

    const handleSubmit = (e) => {
        e.preventDefault()
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

    return (
        <>
            <Navbar />
            <Container
                maxWidth="md"
                sx={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 64px)' }}
            >
                <Typography variant="h6" fontWeight={600} sx={{ py: 2 }}>
                    Trợ lý tư vấn thi Trinity 🎵
                </Typography>

                {/* Message list */}
                <Box sx={{ flex: 1, overflowY: 'auto', pb: 2 }}>
                    {messages.length === 0 && (
                        <Typography color="text.secondary" align="center" mt={4}>
                            Xin chào! Tôi có thể giúp bạn tra cứu chương trình thi, tư vấn cấp độ, và đặt lịch thi Trinity.
                        </Typography>
                    )}
                    {messages.map((msg, i) => (
                        <ChatBubble key={i} role={msg.role} content={msg.content} />
                    ))}
                    {streaming && streamingContent && (
                        <ChatBubble role="assistant" content={streamingContent} streaming />
                    )}
                    <div ref={bottomRef} />
                </Box>

                {/* Confirmation banner */}
                {pendingConfirm && (
                    <ConfirmBanner onConfirm={handleConfirm} onCancel={handleCancel} />
                )}

                {/* Input */}
                <Paper
                    component="form"
                    onSubmit={handleSubmit}
                    elevation={2}
                    sx={{ p: 1, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}
                >
                    <TextField
                        fullWidth
                        size="small"
                        placeholder="Nhập câu hỏi hoặc yêu cầu đặt lịch..."
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
                        InputProps={{
                            endAdornment: (
                                <InputAdornment position="end">
                                    <IconButton type="submit" disabled={!input.trim() || streaming} color="primary">
                                        <SendIcon />
                                    </IconButton>
                                </InputAdornment>
                            ),
                        }}
                    />
                </Paper>
            </Container>
        </>
    )
}
