import { defineConfig } from "@playwright/test";

// End-to-end: the real API (fresh database, sign-in off) and the real
// dashboard, driven through the installed Chrome. `npm run test:e2e`.
export default defineConfig({
  testDir: "e2e",
  fullyParallel: false, // one shared database; tests run in order
  workers: 1,
  timeout: 30_000,
  use: {
    baseURL: "http://localhost:3200", // the dev server serves its scripts only to localhost (allowedDevOrigins),
    channel: "chrome",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "./e2e/start-api.sh",
      url: "http://127.0.0.1:8095/healthz",
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: "npx next dev -p 3200",
      url: "http://localhost:3200",
      env: { API_ORIGIN: "http://127.0.0.1:8095" },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
