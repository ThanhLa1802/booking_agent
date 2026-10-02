import { createTheme } from '@mui/material/styles'

/**
 * Trinity AI — "Editorial Classical" design system.
 *
 * A refined, print-inspired system for a prestigious music institution:
 * Playfair Display for display type, Inter for UI, warm ivory surfaces,
 * a single brass accent used sparingly, hairline rules, restrained motion.
 *
 * Light + dark are produced from the same tokens via getTheme(mode).
 */

const serif =
  '"Playfair Display", "Times New Roman", Georgia, "Songti SC", serif'
const sans =
  '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif'

const typography = {
  fontFamily: sans,
  h1: { fontFamily: serif, fontWeight: 500, fontSize: '2.5rem', lineHeight: 1.15, letterSpacing: '-0.02em' },
  h2: { fontFamily: serif, fontWeight: 500, fontSize: '2rem', lineHeight: 1.2, letterSpacing: '-0.02em' },
  h3: { fontFamily: serif, fontWeight: 500, fontSize: '1.625rem', lineHeight: 1.25, letterSpacing: '-0.015em' },
  h4: { fontFamily: serif, fontWeight: 500, fontSize: '1.375rem', lineHeight: 1.3, letterSpacing: '-0.01em' },
  h5: { fontFamily: serif, fontWeight: 500, fontSize: '1.125rem', lineHeight: 1.35 },
  h6: { fontFamily: sans, fontWeight: 600, fontSize: '1rem', lineHeight: 1.4, letterSpacing: '-0.005em' },
  subtitle1: { fontSize: '1rem', fontWeight: 500, lineHeight: 1.5 },
  subtitle2: { fontSize: '0.875rem', fontWeight: 600, lineHeight: 1.5 },
  body1: { fontSize: '0.9375rem', lineHeight: 1.65, letterSpacing: '-0.003em' },
  body2: { fontSize: '0.875rem', lineHeight: 1.6 },
  button: { textTransform: 'none', fontWeight: 500, letterSpacing: '0.005em' },
  caption: { fontSize: '0.75rem', lineHeight: 1.5, letterSpacing: '0.01em' },
  overline: { fontSize: '0.6875rem', letterSpacing: '0.14em', fontWeight: 600, textTransform: 'uppercase' },
}

const lightPalette = {
  primary: { main: '#7A5C33', light: '#A98A5C', dark: '#5C4526', contrastText: '#FFFFFF' },
  secondary: { main: '#4A4A48', contrastText: '#FFFFFF' },
  background: { default: '#FAF8F4', paper: '#FFFFFF' },
  text: { primary: '#1C1917', secondary: '#57534E', disabled: '#A8A29A' },
  divider: '#E7E1D8',
  success: { main: '#2F6B4F' },
  warning: { main: '#9A6A1E' },
  error: { main: '#B3261E' },
  info: { main: '#3E6B8A' },
}

const darkPalette = {
  primary: { main: '#C9A96A', light: '#DCC492', dark: '#A98A5C', contrastText: '#14110D' },
  secondary: { main: '#B9B2A6', contrastText: '#14110D' },
  background: { default: '#14110D', paper: '#1C1916' },
  text: { primary: '#F5F1EA', secondary: '#A8A29A', disabled: '#6B655D' },
  divider: '#2E2925',
  success: { main: '#7FB79A' },
  warning: { main: '#D8B26A' },
  error: { main: '#E08B85' },
  info: { main: '#8FB2CC' },
}

export function getTheme(mode = 'light') {
  const isDark = mode === 'dark'
  const palette = isDark ? darkPalette : lightPalette

  return createTheme({
    palette: { mode, ...palette },
    typography,
    shape: { borderRadius: 8 },

    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: {
            WebkitFontSmoothing: 'antialiased',
            MozOsxFontSmoothing: 'grayscale',
            textRendering: 'optimizeLegibility',
          },
          '::selection': {
            backgroundColor: isDark ? 'rgba(201,169,106,0.28)' : 'rgba(122,92,51,0.16)',
          },
        },
      },

      MuiAppBar: {
        defaultProps: { elevation: 0, color: 'transparent' },
        styleOverrides: {
          root: ({ theme }) => ({
            backgroundColor: theme.palette.background.default,
            color: theme.palette.text.primary,
            borderBottom: `1px solid ${theme.palette.divider}`,
            backgroundImage: 'none',
          }),
        },
      },

      MuiPaper: {
        defaultProps: { elevation: 0 },
        styleOverrides: {
          root: { backgroundImage: 'none' },
          outlined: ({ theme }) => ({ borderColor: theme.palette.divider }),
        },
      },

      MuiCard: {
        defaultProps: { elevation: 0 },
        styleOverrides: {
          root: ({ theme }) => ({
            backgroundColor: theme.palette.background.paper,
            border: `1px solid ${theme.palette.divider}`,
            borderRadius: 12,
            transition: 'border-color 200ms ease, box-shadow 200ms ease, transform 200ms ease',
            '&:hover': {
              borderColor: theme.palette.primary.light,
              boxShadow: isDark
                ? '0 8px 28px rgba(0,0,0,0.45)'
                : '0 8px 28px rgba(28,25,23,0.07)',
            },
          }),
        },
      },

      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: {
          root: { borderRadius: 6, padding: '9px 18px', fontWeight: 500 },
          containedPrimary: ({ theme }) => ({
            backgroundColor: theme.palette.primary.main,
            '&:hover': { backgroundColor: theme.palette.primary.dark },
          }),
          outlined: ({ theme }) => ({
            borderColor: theme.palette.divider,
            color: theme.palette.text.primary,
            '&:hover': {
              borderColor: theme.palette.primary.main,
              backgroundColor: 'transparent',
            },
          }),
          text: ({ theme }) => ({
            color: theme.palette.text.secondary,
            '&:hover': { color: theme.palette.primary.main },
          }),
          sizeSmall: { padding: '5px 12px', fontSize: '0.8125rem' },
          sizeLarge: { padding: '12px 24px', fontSize: '0.9375rem' },
        },
      },

      MuiTextField: { defaultProps: { variant: 'outlined' } },

      MuiOutlinedInput: {
        styleOverrides: {
          root: ({ theme }) => ({
            backgroundColor: theme.palette.background.paper,
            borderRadius: 8,
            '& .MuiOutlinedInput-notchedOutline': {
              borderColor: theme.palette.divider,
            },
            '&:hover .MuiOutlinedInput-notchedOutline': {
              borderColor: theme.palette.text.disabled,
            },
            '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
              borderColor: theme.palette.primary.main,
              borderWidth: 1,
            },
          }),
        },
      },

      MuiInputLabel: {
        styleOverrides: {
          root: ({ theme }) => ({
            '&.Mui-focused': { color: theme.palette.primary.main },
          }),
        },
      },

      MuiChip: {
        styleOverrides: {
          root: { fontWeight: 500, fontSize: '0.75rem', borderRadius: 6 },
          sizeSmall: { height: 22 },
          filled: () => ({
            backgroundColor: isDark ? 'rgba(201,169,106,0.14)' : '#F1EADD',
            color: isDark ? '#DCC492' : '#6B4F22',
          }),
          outlined: ({ theme }) => ({ borderColor: theme.palette.divider }),
        },
      },

      MuiTable: {
        styleOverrides: {
          root: ({ theme }) => ({
            '& .MuiTableCell-root': {
              borderBottomColor: theme.palette.divider,
              padding: '12px 16px',
              fontSize: '0.875rem',
            },
            '& .MuiTableRow-root:hover': {
              backgroundColor: isDark
                ? 'rgba(201,169,106,0.05)'
                : 'rgba(122,92,51,0.03)',
            },
          }),
        },
      },

      MuiTableHead: {
        styleOverrides: {
          root: ({ theme }) => ({
            '& .MuiTableCell-root': {
              fontWeight: 600,
              color: theme.palette.text.secondary,
              fontSize: '0.6875rem',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              borderBottomColor: theme.palette.divider,
            },
          }),
        },
      },

      MuiDialog: {
        styleOverrides: {
          paper: ({ theme }) => ({
            borderRadius: 14,
            border: `1px solid ${theme.palette.divider}`,
            backgroundImage: 'none',
          }),
        },
      },

      MuiTabs: {
        styleOverrides: {
          indicator: ({ theme }) => ({ height: 2, backgroundColor: theme.palette.primary.main }),
        },
      },

      MuiTab: {
        styleOverrides: {
          root: ({ theme }) => ({
            textTransform: 'none',
            fontWeight: 500,
            fontSize: '0.875rem',
            color: theme.palette.text.secondary,
            '&.Mui-selected': { color: theme.palette.text.primary },
          }),
        },
      },

      MuiSelect: {
        styleOverrides: {
          outlined: ({ theme }) => ({ backgroundColor: theme.palette.background.paper }),
        },
      },

      MuiListItemButton: {
        styleOverrides: {
          root: () => ({
            borderRadius: 8,
            '&.Mui-selected': {
              backgroundColor: isDark ? 'rgba(201,169,106,0.14)' : 'rgba(122,92,51,0.08)',
              '&:hover': {
                backgroundColor: isDark ? 'rgba(201,169,106,0.2)' : 'rgba(122,92,51,0.12)',
              },
            },
          }),
        },
      },

      MuiAlert: {
        styleOverrides: { root: { borderRadius: 8, fontSize: '0.875rem' } },
      },

      MuiAvatar: {
        styleOverrides: { root: { fontSize: '0.8125rem', fontWeight: 500 } },
      },

      MuiToolbar: {
        styleOverrides: {
          root: { minHeight: 60, '@media (min-width: 600px)': { minHeight: 60 } },
        },
      },

      MuiTooltip: {
        styleOverrides: {
          tooltip: ({ theme }) => ({
            backgroundColor: theme.palette.text.primary,
            color: theme.palette.background.paper,
            fontSize: '0.75rem',
            borderRadius: 6,
          }),
        },
      },

      MuiLink: {
        defaultProps: { underline: 'hover' },
        styleOverrides: {
          root: ({ theme }) => ({ color: theme.palette.primary.main, fontWeight: 500 }),
        },
      },

      MuiDivider: {
        styleOverrides: {
          root: ({ theme }) => ({ borderColor: theme.palette.divider }),
        },
      },
    },
  })
}

export default getTheme()
