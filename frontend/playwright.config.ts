import { defineConfig } from "@playwright/test";

const isWindows = process.platform === "win32";
const python = isWindows ? ".venv\\Scripts\\python.exe" : ".venv/bin/python";

// Set E2E_BASE_URL to test a deployed site (no local servers are started then).
const remote = process.env.E2E_BASE_URL;

export default defineConfig({
  testDir: "e2e",
  timeout: 30_000,
  use: {
    baseURL: remote ?? "http://127.0.0.1:5173",
    // Uses an installed Edge/Chrome rather than downloading a browser.
    // Override with PLAYWRIGHT_CHANNEL (e.g. "chrome", or "" for bundled Chromium).
    channel: process.env.PLAYWRIGHT_CHANNEL ?? "msedge",
    viewport: { width: 1280, height: 800 },
  },
  webServer: remote
    ? undefined
    : [
    {
      command: `${python} -m uvicorn app.main:app --host 127.0.0.1 --port 8000`,
      cwd: "../backend",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: true,
    },
    {
      command: "npm run dev",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: true,
    },
  ],
});
