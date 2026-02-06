import colors from 'tailwindcss/colors'

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: '#0a0a0a',
          subtle: '#0f0f0f',
        },
        panel: {
          DEFAULT: '#1a1a1a',
          elevated: '#202020',
        },
        border: '#262626',
        text: {
          DEFAULT: '#f5f5f5',
          muted: '#b3b3b3',
          subtle: '#8a8a8a',
        },

        // Semantic palette for the Darwin AI UI.
        primary: {
          ...colors.emerald,
          DEFAULT: colors.emerald[400],
        },
        danger: {
          ...colors.red,
          DEFAULT: colors.red[400],
        },
        warning: {
          ...colors.amber,
          DEFAULT: colors.amber[400],
        },
        info: {
          ...colors.cyan,
          DEFAULT: colors.cyan[400],
        },
      },
      fontFamily: {
        sans: [
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          '"Helvetica Neue"',
          'Arial',
          '"Noto Sans"',
          '"Liberation Sans"',
          '"Apple Color Emoji"',
          '"Segoe UI Emoji"',
          '"Segoe UI Symbol"',
          '"Noto Color Emoji"',
        ],
        mono: [
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'Monaco',
          'Consolas',
          '"Liberation Mono"',
          '"Courier New"',
          'monospace',
        ],
      },
    },
  },
  plugins: [],
}
