/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        'harbor-bg': '#0D1117',
        'harbor-surface': '#161B22',
        'harbor-border': '#30363D',
        'harbor-text': '#E6EDF3',
        'harbor-green': '#4ADE80',
        'harbor-amber': '#FBBF24',
        'harbor-red': '#F87171',
        'harbor-blue': '#60A5FA',
        'harbor-cyan': '#22D3EE',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
