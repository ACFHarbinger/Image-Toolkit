/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        // Generated from gui/src/theming/tokens/{light,dark}.json via
        // `npm run gen:theme-tokens` — the shared design tokens (W0-07).
        it: {
          accent: "var(--it-color-accent)",
          "accent-hover": "var(--it-color-accent-hover)",
          "accent-pressed": "var(--it-color-accent-pressed)",
          surface: "var(--it-color-surface)",
          "window-bg": "var(--it-color-window-bg)",
          text: "var(--it-color-text)",
          "muted-text": "var(--it-color-muted-text)",
          border: "var(--it-color-border)",
        },
      },
    },
  },
  plugins: [],
};
