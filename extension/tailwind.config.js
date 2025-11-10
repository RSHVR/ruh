/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  theme: {
    extend: {
      colors: {
        safe: '#10b981',      // green
        lowRisk: '#84cc16',    // lime
        moderate: '#f59e0b',   // amber
        highRisk: '#ef4444',   // red
        dangerous: '#dc2626'   // dark red
      }
    }
  },
  plugins: []
};
