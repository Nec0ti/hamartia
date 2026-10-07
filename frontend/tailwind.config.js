/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Canonical True Dark palette from the project design system.
        canvas: {
          base: '#09090b',   // zinc-950 background
          panel: '#18181b',  // zinc-900 elevated panel
          raise: '#1c1c21',  // zinc-800 raised border surface
          line: '#27272a',  // zinc-800 subtle borders
          text: '#d4d4d8',  // zinc-300 primary text
          muted: '#a1a1aa', // zinc-400 secondary text
          accent: '#ef4444', // crimson fatal-flaw accent
          amber: '#f59e0b',  // amber streak/energy accent
          emerald: '#10b981', // emerald correct accent
          indigo: '#818cf8',  // neon indigo cosmos accent
          cyan: '#22d3ee',    // neon cyan cosmos accent
        },
      },
      boxShadow: {
        glow: '0 0 24px rgba(129, 140, 248, 0.25)',
        crimson: '0 0 24px rgba(239, 68, 68, 0.35)',
      },
      borderRadius: {
        xl: '1rem',
        '2xl': '1.25rem',
      },
    },
  },
  plugins: [],
}
