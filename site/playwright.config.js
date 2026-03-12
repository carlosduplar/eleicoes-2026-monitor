// @ts-check
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '../qa/tests',
  timeout: 30_000,
  expect: {
    timeout: 10_000,
  },
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: 'http://127.0.0.1:4173/eleicoes-2026-monitor/',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'npm run preview -- --host 127.0.0.1 --port 4173 --strictPort',
    url: 'http://127.0.0.1:4173/eleicoes-2026-monitor/',
    timeout: 120_000,
    reuseExistingServer: !process.env.CI,
    cwd: '.',
  },
  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' },
    },
  ],
});

