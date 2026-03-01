/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        'teacher-pilot': {
          primary: '#4F46E5', // Indigo
          secondary: '#10B981', // Emerald
          warm: '#F59E0B', // Amber for Marimba
        }
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
}