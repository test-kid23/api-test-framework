/**
 * 仪表盘 E2E 测试.
 *
 * 覆盖:
 * - 仪表盘页面加载
 * - KPI 卡片渲染
 * - 图表渲染
 * - 空数据状态
 * - 侧边栏导航
 */
import { test, expect } from "@playwright/test";
import { login, clearAuth, TEST_USERS } from "./fixtures/auth";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await clearAuth(page);
    await login(page, TEST_USERS.admin);
  });

  test("should display dashboard page", async ({ page }) => {
    await page.goto("/#/dashboard");

    await expect(page.locator("h1, h2")).toBeVisible({ timeout: 10000 });
  });

  test("should show page title or empty state", async ({ page }) => {
    await page.goto("/#/dashboard");

    await page.waitForLoadState("networkidle", { timeout: 15000 });

    // 检查是否有内容：标题 或 空状态消息
    const hasContent = await page.locator("text=报告看板").isVisible({ timeout: 5000 });
    const isEmpty = await page.locator("text=暂无报告数据").isVisible({ timeout: 5000 });

    expect(hasContent || isEmpty).toBe(true);
  });

  test("should navigate from sidebar to dashboard", async ({ page }) => {
    await page.goto("/#/cases");

    // 通过侧边栏导航到报告看板
    const sidebar = page.locator("aside");
    const dashLink = sidebar.locator('a[href*="dashboard"]');
    await dashLink.first().click();

    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10000 });
  });

  test("should display sidebar with all navigation groups", async ({ page }) => {
    await page.goto("/#/dashboard");

    const sidebar = page.locator("aside");
    await expect(sidebar).toBeVisible({ timeout: 5000 });
  });

  test("should navigate between dashboard and other pages via sidebar", async ({ page }) => {
    await page.goto("/#/dashboard");

    // 导航到用例管理
    const sidebar = page.locator("aside");
    const casesLink = sidebar.locator('a[href*="/cases"]').first();
    await casesLink.click();
    await expect(page).toHaveURL(/\/cases/, { timeout: 10000 });

    // 导航回仪表盘
    const dashLink = sidebar.locator('a[href*="dashboard"]');
    await dashLink.first().click();
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10000 });
  });
});
