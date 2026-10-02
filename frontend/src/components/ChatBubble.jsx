import { Avatar, Box } from '@mui/material'
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/**
 * ChatBubble — minimal, typography-first.
 *
 * User  : compact pill on the right, near-black background.
 * Bot   : avatar on the left, full-width text, no bubble.
 *         Avatar breathes (fermata pulse) while streaming.
 */
export default function ChatBubble({ role, content, streaming = false }) {
  const isUser = role === 'user'

  if (isUser) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'flex-end',
          mb: 3,
          px: 0.5,
        }}
      >
        <Box
          sx={{
            px: 2.5,
            py: 1.25,
            maxWidth: '72%',
            bgcolor: '#171717',
            color: '#FCFCFB',
            borderRadius: '20px 20px 4px 20px',
            fontSize: '0.9375rem',
            lineHeight: 1.6,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {content}
        </Box>
      </Box>
    )
  }

  // ── Bot message ────────────────────────────────────────────────
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'flex-start',
        mb: 3,
        px: 0.5,
        gap: 1.5,
      }}
    >
      <Avatar
        className={streaming ? 'ai-avatar-streaming' : ''}
        sx={{
          bgcolor: '#F0ECE6',
          color: '#A0825C',
          width: 32,
          height: 32,
          mt: 0.25,
          flexShrink: 0,
        }}
      >
        <SmartToyOutlinedIcon sx={{ fontSize: 16 }} />
      </Avatar>

      <Box
        sx={{
          flex: 1,
          minWidth: 0,
          fontSize: '0.9375rem',
          lineHeight: 1.7,
          color: 'text.primary',
          wordBreak: 'break-word',

          // ── Markdown elements ──────────────────────────────
          '& p': { m: 0, mb: 1 },
          '& p:last-child': { mb: 0 },
          '& ul, & ol': { pl: 2.5, my: 0.5 },
          '& li': { mb: 0.375, lineHeight: 1.65 },
          '& li > p': { mb: 0 },
          '& h1, & h2, & h3': {
            fontWeight: 600,
            letterSpacing: '-0.01em',
          },
          '& h1': { fontSize: '1.15rem', mt: 2, mb: 0.75 },
          '& h2': { fontSize: '1.05rem', mt: 1.5, mb: 0.5 },
          '& h3': { fontSize: '0.9375rem', mt: 1, mb: 0.5 },
          '& strong': { fontWeight: 600 },

          // Inline code
          '& :not(pre) > code': {
            fontFamily: '"JetBrains Mono", "Fira Code", monospace',
            bgcolor: '#F0ECE6',
            color: '#6B5E4F',
            px: 0.625,
            py: 0.125,
            borderRadius: '4px',
            fontSize: '0.82em',
          },

          // Code blocks
          '& pre': {
            bgcolor: '#1A1A1C',
            color: '#E0DED8',
            p: 2,
            borderRadius: '8px',
            overflow: 'auto',
            my: 1.25,
            fontSize: '0.8125rem',
            lineHeight: 1.6,
            '& code': {
              bgcolor: 'transparent',
              color: 'inherit',
              p: 0,
              fontSize: 'inherit',
            },
          },

          // Blockquote
          '& blockquote': {
            borderLeft: '2px solid #A0825C',
            pl: 2,
            ml: 0,
            my: 0.75,
            color: 'text.secondary',
            fontStyle: 'italic',
          },

          // Tables
          '& table': {
            borderCollapse: 'collapse',
            width: '100%',
            my: 1,
            fontSize: '0.8125rem',
          },
          '& th, & td': {
            border: '1px solid #EBE9E6',
            px: 1.25,
            py: 0.625,
            textAlign: 'left',
          },
          '& th': {
            bgcolor: '#F5F4F2',
            fontWeight: 600,
            color: '#707070',
            fontSize: '0.75rem',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          },

          // Dividers
          '& hr': {
            my: 1.5,
            border: 'none',
            borderTop: '1px solid #EBE9E6',
          },
        }}
      >
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content || ''}</ReactMarkdown>
        {streaming && (
          <Box
            component="span"
            sx={{
              display: 'inline-block',
              width: 2,
              height: '1.1em',
              bgcolor: '#A0825C',
              ml: '2px',
              verticalAlign: 'text-bottom',
              '@keyframes blink': {
                '0%, 100%': { opacity: 1 },
                '50%': { opacity: 0.25 },
              },
              animation: 'blink 0.8s step-start infinite',
            }}
          />
        )}
      </Box>
    </Box>
  )
}
