import { createTheme } from '@mui/material/styles'

/**
 * Trinity AI — "Rest" design system.
 *
 * Minimalist. Every element has a reason to exist.
 * Spacing is the primary design tool. Typography does the heavy lifting.
 * One accent colour: warm brass — used sparingly like a fermata in a score.
 */
const theme = createTheme({
  palette: {
    mode: 'light',
    background: {
      default: '#FCFCFB',
      paper: '#F5F4F2',
    },
    text: {
      primary: '#171717',
      secondary: '#707070',
    },
    primary: {
      main: '#A0825C',
      light: '#C4AC84',
      dark: '#7A6240',
      contrastText: '#FCFCFB',
    },
    secondary: {
      main: '#6B5E4F',
      light: '#9E8F80',
      dark: '#4A3F34',
      contrastText: '#FCFCFB',
    },
    divider: '#EBE9E6',
    error: { main: '#C25450' },
    success: { main: '#5C8A67' },
    warning: { main: '#C49450' },
    info: { main: '#6B8F9E' },
  },

  typography: {
    fontFamily:
      '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    h4: {
      fontSize: '1.5rem',
      fontWeight: 600,
      letterSpacing: '-0.02em',
      lineHeight: 1.3,
    },
    h5: {
      fontSize: '1.25rem',
      fontWeight: 500,
      letterSpacing: '-0.01em',
      lineHeight: 1.35,
    },
    h6: {
      fontSize: '1rem',
      fontWeight: 600,
      lineHeight: 1.4,
    },
    body1: {
      fontSize: '1rem',
      lineHeight: 1.6,
      letterSpacing: '-0.003em',
    },
    body2: {
      fontSize: '0.875rem',
      lineHeight: 1.55,
    },
    caption: {
      fontSize: '0.75rem',
      lineHeight: 1.5,
    },
    button: {
      textTransform: 'none',
      fontWeight: 500,
      letterSpacing: '-0.005em',
    },
  },

  shape: {
    borderRadius: 8,
  },

  shadows: [
    'none',
    '0 1px 2px rgba(0,0,0,0.04)',
    '0 2px 8px rgba(0,0,0,0.05)',
    '0 4px 16px rgba(0,0,0,0.06)',
    ...Array(22).fill('none'),
  ],

  components: {
    // ── AppBar — flat, transparent ───────────────────────────────────────
    MuiAppBar: {
      defaultProps: { elevation: 0, color: 'inherit' },
      styleOverrides: {
        root: {
          backgroundColor: '#FCFCFB',
          borderBottom: '1px solid #EBE9E6',
        },
      },
    },

    // ── Paper — subtle, almost indistinguishable from background ─────────
    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
        outlined: {
          borderColor: '#EBE9E6',
        },
      },
    },

    // ── Card — clean, minimal lift on hover ──────────────────────────────
    MuiCard: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          backgroundColor: '#F5F4F2',
          border: '1px solid #EBE9E6',
          borderRadius: 10,
          transition: 'box-shadow 0.2s ease, transform 0.2s ease',
          '&:hover': {
            boxShadow: '0 4px 20px rgba(0,0,0,0.06)',
            transform: 'translateY(-1px)',
          },
        },
      },
    },

    // ── Button — pill shapes, restrained ─────────────────────────────────
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: {
          borderRadius: 100,
          padding: '10px 24px',
          fontSize: '0.875rem',
        },
        containedPrimary: {
          backgroundColor: '#A0825C',
          '&:hover': { backgroundColor: '#8B6F4A' },
        },
        outlined: {
          borderColor: '#EBE9E6',
          color: '#171717',
          '&:hover': {
            borderColor: '#A0825C',
            backgroundColor: 'transparent',
          },
        },
        text: {
          color: '#707070',
          '&:hover': {
            backgroundColor: 'rgba(160,130,92,0.08)',
          },
        },
        sizeSmall: {
          padding: '6px 16px',
          fontSize: '0.8125rem',
        },
        sizeLarge: {
          padding: '14px 32px',
          fontSize: '0.9375rem',
        },
      },
    },

    // ── TextField — bottom-border, minimal ───────────────────────────────
    MuiTextField: {
      defaultProps: { variant: 'outlined' },
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            backgroundColor: '#FCFCFB',
            borderRadius: 8,
            fontSize: '0.9375rem',
            '& fieldset': { borderColor: '#EBE9E6' },
            '&:hover fieldset': { borderColor: '#C4AC84' },
            '&.Mui-focused fieldset': {
              borderColor: '#A0825C',
              borderWidth: 1,
            },
          },
          '& .MuiInputLabel-root.Mui-focused': {
            color: '#A0825C',
          },
        },
      },
    },

    // ── Chip — soft, rounded ─────────────────────────────────────────────
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 500,
          fontSize: '0.75rem',
        },
        filled: {
          backgroundColor: '#F0ECE6',
          color: '#6B5E4F',
        },
        outlined: {
          borderColor: '#EBE9E6',
        },
      },
    },

    // ── Table — clean, airy ──────────────────────────────────────────────
    MuiTable: {
      styleOverrides: {
        root: {
          '& .MuiTableCell-root': {
            borderBottomColor: '#F0ECE6',
            padding: '12px 16px',
            fontSize: '0.875rem',
          },
          '& .MuiTableRow-root:hover': {
            backgroundColor: 'rgba(160,130,92,0.04)',
          },
        },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          '& .MuiTableCell-root': {
            fontWeight: 600,
            color: '#707070',
            fontSize: '0.75rem',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            borderBottomColor: '#EBE9E6',
          },
        },
      },
    },

    // ── Dialog — clean, minimal ──────────────────────────────────────────
    MuiDialog: {
      styleOverrides: {
        paper: {
          borderRadius: 12,
          border: '1px solid #EBE9E6',
        },
      },
    },

    // ── Tabs — subtle underline ──────────────────────────────────────────
    MuiTabs: {
      styleOverrides: {
        indicator: {
          height: 2,
          backgroundColor: '#A0825C',
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 500,
          fontSize: '0.875rem',
          color: '#707070',
          '&.Mui-selected': { color: '#171717' },
        },
      },
    },

    // ── Select / Menu ────────────────────────────────────────────────────
    MuiSelect: {
      styleOverrides: {
        outlined: {
          backgroundColor: '#FCFCFB',
        },
      },
    },
    MuiMenuItem: {
      styleOverrides: {
        root: {
          fontSize: '0.875rem',
        },
      },
    },

    // ── Alert — toned down ───────────────────────────────────────────────
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          fontSize: '0.875rem',
        },
      },
    },

    // ── Avatar — subtle background ───────────────────────────────────────
    MuiAvatar: {
      styleOverrides: {
        root: {
          fontSize: '0.875rem',
          fontWeight: 500,
        },
      },
    },

    // ── Toolbar — reduce min-height ──────────────────────────────────────
    MuiToolbar: {
      styleOverrides: {
        root: {
          minHeight: 56,
          '@media (min-width: 600px)': { minHeight: 56 },
        },
      },
    },
  },
})

export default theme
