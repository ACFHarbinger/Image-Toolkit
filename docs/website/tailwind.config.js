/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,ts,tsx,astro}",
    "./src/frameworks/astro/**/*.astro",
  ],
  darkMode: ["selector", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        accent: "var(--accent)",
        "accent-2": "var(--accent-2)",
      },
    },
  },
  plugins: [],
};
