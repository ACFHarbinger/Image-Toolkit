/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,ts,tsx,astro}",
    "./stories/**/*.tsx",
    // Tailwind utility classes the React island needs are authored on the
    // *real* frontend/src/components/common/* files (imported verbatim, not
    // copied — see ComponentGallery.tsx) and stories/*.stories.tsx, so both
    // must be scanned too, or those classes never get generated here.
    "../../frontend/src/components/**/*.tsx",
  ],
  darkMode: ["selector", '[data-theme="dark"]'],
  // The Vue chrome (theme.css) owns resets/base element styles already —
  // Tailwind here exists only to generate utility classes for the React
  // island, so skip preflight to avoid it fighting the hand-tuned chrome.
  corePlugins: { preflight: false },
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
