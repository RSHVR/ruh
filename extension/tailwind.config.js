/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  theme: {
    extend: {
      colors: {
        // Brand colors (mapped to CSS variables)
        brand: {
          primary: 'var(--color-primary)',       // #e8dcc8 Soft Sand
          secondary: 'var(--color-secondary)',   // #a8b89f Sage Green
          accent: 'var(--color-accent)',         // #c9b5a0 Warm Taupe
        },
        // Semantic status colors
        safe: 'var(--color-safe)',               // #9bb88f Safe Green
        caution: 'var(--color-caution)',         // #d4a574 Caution Amber
        alert: 'var(--color-alert)',             // #c18a72 Alert Rust
        // Background colors
        surface: {
          primary: 'var(--color-bg-primary)',    // #fffbf5 Cream
          secondary: 'var(--color-bg-secondary)', // #f5f0e8 Pale Linen
        },
        // Text colors
        ink: {
          primary: 'var(--color-text)',          // #3a3633 Deep Charcoal
          secondary: 'var(--color-text-secondary)', // #5a534e Medium Gray (WCAG AA)
          muted: '#706a65',                      // Tertiary text (4.5:1 contrast)
        },
      }
    }
  },
  plugins: []
};
