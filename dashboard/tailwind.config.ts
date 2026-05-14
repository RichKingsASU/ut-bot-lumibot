/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'bg-primary': '#0d1117',
        'bg-secondary': '#161b22',
        'bg-tertiary': '#21262d',
        'border-color': '#30363d',
        'text-primary': '#e6edf3',
        'text-muted': '#8b949e',
        'accent-green': '#3fb950',
        'accent-red': '#f85149',
        'accent-blue': '#58a6ff',
        'accent-amber': '#e3b341',
        'accent-purple': '#6e40c9',
        'space': '#09090b',
        'surface-0': '#000000',
        'surface-1': '#18181b',
        'surface-2': '#27272a',
        'surface-3': '#3f3f46',
        'vibrant': '#fafafa',
        'secondary': '#a1a1aa',
        'dim': '#52525b',
        'border-muted': 'rgba(255,255,255,0.08)',
        'border-active': 'rgba(255,255,255,0.2)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    },
  },
  plugins: [],
}
