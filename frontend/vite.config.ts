/// <reference types="vitest/config" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    strictPort: true,
  },
  build: {
    outDir: "build",
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/setupTests.ts"],
    exclude: ["e2e/**", "node_modules/**"],
  },
});
