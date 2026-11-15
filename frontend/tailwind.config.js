/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Neutral dark palette shared across all study views.
        canvas: {
          base: '#09090b',   // zinc-950 background
          panel: '#18181b',  // zinc-900 elevated panel
          raise: '#1c1c21',  // zinc-800 raised border surface
          line: '#27272a',  // zinc-800 subtle borders
          text: '#f4f4f5',  // zinc-100 primary text
          muted: '#a1a1aa', // zinc-400 secondary text
          accent: '#e4e4e7', // monochrome interactive accent
          amber: '#d4d4d8',
          emerald: '#d4d4d8',
          indigo: '#d4d4d8',
          cyan: '#d4d4d8',
        },
      },
      boxShadow: {
        glow: '0 0 24px rgba(255, 255, 255, 0.08)',
        crimson: '0 0 24px rgba(255, 255, 255, 0.08)',
      },
      borderRadius: {
        xl: '1rem',
        '2xl': '1.25rem',
      },
    },
  },
  plugins: [],
}
