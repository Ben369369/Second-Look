import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const backend = process.env.SECOND_LOOK_BACKEND_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: { "/api": backend },
  },
  test: {
    include: ["tests/**/*.test.ts"],
  },
});
