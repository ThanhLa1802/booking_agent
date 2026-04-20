import { Avatar, Box } from '@mui/material'
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined'
import PersonOutlinedIcon from '@mui/icons-material/PersonOutlined'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/**
 * A single chat bubble — ChatGPT/Gemini style.
 *   User  : bubble on the right with avatar.
 *   Bot   : avatar + full-width text, no bubble, blinking cursor while streaming.
 */
export default function ChatBubble({ role, content, streaming = false }) {
    const isUser = role === 'user'

    if (isUser) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'flex-start', mb: 2.5, gap: 1.5 }}>
                <Box
                    sx={{
                        px: 2.5,
                        py: 1.5,
                        maxWidth: '75%',
                        bgcolor: 'primary.main',
                        color: 'primary.contrastText',
                        borderRadius: '20px 20px 4px 20px',
                        fontSize: '0.9rem',
                        lineHeight: 1.65,
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                    }}
                >
                    {content}
                </Box>
                <Avatar sx={{ bgcolor: 'primary.dark', width: 34, height: 34, mt: 0.25, flexShrink: 0 }}>
                    <PersonOutlinedIcon sx={{ fontSize: 18 }} />
                </Avatar>
            </Box>
        )
    }

    // ── Bot message ──────────────────────────────────────────────
    return (
        <Box sx={{ display: 'flex', alignItems: 'flex-start', mb: 2.5, gap: 1.5 }}>
            <Avatar sx={{ bgcolor: 'secondary.main', width: 34, height: 34, mt: 0.25, flexShrink: 0 }}>
                <SmartToyOutlinedIcon sx={{ fontSize: 18 }} />
            </Avatar>

            <Box
                sx={{
                    flex: 1,
                    minWidth: 0,
                    fontSize: '0.9rem',
                    lineHeight: 1.75,
                    textAlign: 'left',
                    color: 'text.primary',
                    wordBreak: 'break-word',

                    // Paragraphs
                    '& p': { m: 0, mb: 1.25 },
                    '& p:last-child': { mb: 0 },

                    // Lists
                    '& ul, & ol': { pl: 2.5, my: 0.75 },
                    '& li': { mb: 0.5, lineHeight: 1.7 },
                    '& li > p': { mb: 0 },

                    // Headings
                    '& h1': { fontSize: '1.25rem', fontWeight: 700, mt: 2, mb: 1 },
                    '& h2': { fontSize: '1.1rem', fontWeight: 700, mt: 1.5, mb: 0.75 },
                    '& h3': { fontSize: '1rem', fontWeight: 600, mt: 1.25, mb: 0.5 },

                    // Inline code
                    '& :not(pre) > code': {
                        fontFamily: '"JetBrains Mono", "Fira Code", monospace',
                        bgcolor: 'rgba(0,0,0,0.06)',
                        color: 'error.dark',
                        px: 0.75,
                        py: 0.15,
                        borderRadius: '4px',
                        fontSize: '0.82em',
                    },

                    // Code blocks
                    '& pre': {
                        bgcolor: '#1a1a2e',
                        color: '#e0e0e0',
                        p: 2,
                        borderRadius: '8px',
                        overflow: 'auto',
                        my: 1.5,
                        fontSize: '0.83rem',
                        lineHeight: 1.6,
                        '& code': { bgcolor: 'transparent', color: 'inherit', p: 0, fontSize: 'inherit' },
                    },

                    // Blockquote
                    '& blockquote': {
                        borderLeft: '3px solid',
                        borderColor: 'primary.light',
                        pl: 2,
                        ml: 0,
                        my: 1,
                        color: 'text.secondary',
                        fontStyle: 'italic',
                    },

                    // Tables
                    '& table': { borderCollapse: 'collapse', width: '100%', my: 1.5, fontSize: '0.87rem' },
                    '& th, & td': {
                        border: '1px solid',
                        borderColor: 'divider',
                        px: 1.5,
                        py: 0.75,
                        textAlign: 'left',
                    },
                    '& th': { bgcolor: 'grey.100', fontWeight: 600 },

                    // HR
                    '& hr': { my: 2, borderColor: 'divider' },

                    // Strong / em
                    '& strong': { fontWeight: 700 },

                    // Blinking cursor
                    '@keyframes blink': { '0%, 100%': { opacity: 1 }, '50%': { opacity: 0 } },
                }}
            >
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{content || ''}</ReactMarkdown>
                {streaming && (
                    <Box
                        component="span"
                        sx={{
                            display: 'inline-block',
                            width: '2px',
                            height: '1em',
                            bgcolor: 'text.primary',
                            ml: '2px',
                            verticalAlign: 'text-bottom',
                            animation: 'blink 0.65s step-start infinite',
                        }}
                    />
                )}
            </Box>
        </Box>
    )
}
