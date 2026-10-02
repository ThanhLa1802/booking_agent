import { Avatar, Box } from '@mui/material'
import { alpha } from '@mui/material/styles'
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/**
 * ChatBubble — typography-first.
 *
 * User : compact bubble on the right, brass fill.
 * Bot  : brass monogram on the left, full-width text, no bubble.
 *        Avatar breathes (fermata pulse) while streaming.
 */
export default function ChatBubble({ role, content, streaming = false }) {
  const isUser = role === 'user'

  if (isUser) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 3, px: 0.5 }}>
        <Box
          sx={{
            px: 2.25,
            py: 1.25,
            maxWidth: '72%',
            bgcolor: 'primary.main',
            color: 'primary.contrastText',
            borderRadius: '14px 14px 4px 14px',
            fontSize: '0.9375rem',
            lineHeight: 1.6,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            boxShadow: (theme) =>
              theme.palette.mode === 'dark'
                ? 'none'
                : '0 2px 10px rgba(122,92,51,0.18)',
          }}
        >
          {content}
        </Box>
      </Box>
    )
  }

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'flex-start',
        mb: 3.5,
        px: 0.5,
        gap: 1.5,
      }}
    >
      <Avatar
        className={streaming ? 'ai-avatar-streaming' : ''}
        sx={{
          bgcolor: (theme) => alpha(theme.palette.primary.main, theme.palette.mode === 'dark' ? 0.2 : 0.12),
          color: 'primary.main',
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

          '& p': { m: 0, mb: 1 },
          '& p:last-child': { mb: 0 },
          '& ul, & ol': { pl: 2.5, my: 0.5 },
          '& li': { mb: 0.375, lineHeight: 1.65 },
          '& li > p': { mb: 0 },
          '& h1, & h2, & h3': {
            fontFamily: '"Playfair Display", Georgia, serif',
            fontWeight: 500,
            letterSpacing: '-0.01em',
          },
          '& h1': { fontSize: '1.25rem', mt: 2, mb: 0.75 },
          '& h2': { fontSize: '1.1rem', mt: 1.5, mb: 0.5 },
          '& h3': { fontSize: '1rem', mt: 1, mb: 0.5 },
          '& strong': { fontWeight: 600 },
          '& a': { color: 'primary.main' },

          '& :not(pre) > code': {
            fontFamily: '"JetBrains Mono", "Fira Code", monospace',
            bgcolor: (theme) => alpha(theme.palette.primary.main, 0.1),
            color: 'primary.main',
            px: 0.625,
            py: 0.125,
            borderRadius: '4px',
            fontSize: '0.82em',
          },

          '& pre': {
            bgcolor: 'text.primary',
            color: 'background.default',
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

          '& blockquote': {
            borderLeft: '2px solid',
            borderColor: 'primary.main',
            pl: 2,
            ml: 0,
            my: 0.75,
            color: 'text.secondary',
            fontStyle: 'italic',
          },

          '& table': {
            borderCollapse: 'collapse',
            width: '100%',
            my: 1,
            fontSize: '0.8125rem',
          },
          '& th, & td': {
            border: '1px solid',
            borderColor: 'divider',
            px: 1.25,
            py: 0.625,
            textAlign: 'left',
          },
          '& th': {
            bgcolor: 'background.default',
            fontWeight: 600,
            color: 'text.secondary',
            fontSize: '0.6875rem',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
          },

          '& hr': {
            my: 1.5,
            border: 'none',
            borderTop: '1px solid',
            borderColor: 'divider',
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
              bgcolor: 'primary.main',
              ml: '2px',
              verticalAlign: 'text-bottom',
              '@keyframes blink': {
                '0%, 100%': { opacity: 1 },
                '50%': { opacity: 0.2 },
              },
              animation: 'blink 0.9s step-start infinite',
            }}
          />
        )}
      </Box>
    </Box>
  )
}
