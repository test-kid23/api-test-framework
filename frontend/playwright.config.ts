import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E 测试配置.
 *
 * 使用方式:
 *   npx playwright test                  # 运行所有测试
 *   npx playwright test --ui             # UI 模式
 *   npx playwright test --headed         # 有头模式
 *   npm run test:e2e                     # npm script 方式
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ["html", { outputFolder: "playwright-report" }],
    ["list"],
  ],

  timeout: 30000,
  expect: { timeout: 10000 },

  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"] },
    },
    {
      name: "webkit",
      use: { ...devices["Desktop Safari"] },
    },
  ],

  // 本地开发服务器
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
});
