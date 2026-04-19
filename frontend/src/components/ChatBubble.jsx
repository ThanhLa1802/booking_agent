import { Box, Paper, Typography, CircularProgress } from '@mui/material'
import ConstructionIcon from '@mui/icons-material/Construction'
import ReactMarkdown from 'react-markdown'

/**
 * A single chat bubble (user or assistant).
 * Assistant bubbles render markdown. Streaming bubbles show a spinner.
 */
export default function ChatBubble({ role, content, streaming = false }) {
    const isUser = role === 'user'

    return (
        <Box
            sx={{
                display: 'flex',
                justifyContent: isUser ? 'flex-end' : 'flex-start',
                mb: 1.5,
            }}
        >
            <Paper
                elevation={0}
                sx={{
                    px: 2,
                    py: 1.5,
                    maxWidth: '80%',
                    borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
                    bgcolor: isUser ? 'primary.main' : 'grey.100',
                    color: isUser ? 'primary.contrastText' : 'text.primary',
                }}
            >
                {isUser ? (
                    <Typography variant="body2">{content}</Typography>
                ) : (
                    <Box sx={{ '& p': { m: 0 }, '& p + p': { mt: 1 }, fontSize: '0.875rem' }}>
                        <ReactMarkdown>{content || ''}</ReactMarkdown>
                        {streaming && (
                            <CircularProgress size={12} sx={{ ml: 1, verticalAlign: 'middle' }} />
                        )}
                    </Box>
                )}
            </Paper>
        </Box>
    )
}
