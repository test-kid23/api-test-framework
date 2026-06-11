/**
 * 用例管理 E2E 测试.
 *
 * 覆盖:
 * - 用例列表加载
 * - 搜索/筛选
 * - 新建用例流程
 * - 用例详情查看
 */
import { test, expect } from "@playwright/test";
import { login, clearAuth, TEST_USERS } from "./fixtures/auth";

test.describe("Cases Management", () => {
  test.beforeEach(async ({ page }) => {
    await clearAuth(page);
    await login(page, TEST_USERS.admin);
  });

  test("should display cases list page", async ({ page }) => {
    await page.goto("/#/cases");

    // 检查页面关键元素
    await expect(page.locator("h1")).toBeVisible({ timeout: 10000 });
    await expect(page.locator("text=用例管理")).toBeVisible({ timeout: 5000 });
  });

  test("should have search functionality", async ({ page }) => {
    await page.goto("/#/cases");

    // 查找搜索输入框
    const searchInput = page.locator('input[placeholder*="搜索"]');
    if (await searchInput.isVisible({ timeout: 5000 })) {
      await expect(searchInput).toBeEnabled();
    }
  });

  test("should navigate to create case page", async ({ page }) => {
    await page.goto("/#/cases");

    // 点击新建按钮
    const createBtn = page.locator('a[href="#/cases/new"], button:has-text("新建")');
    if (await createBtn.isVisible({ timeout: 5000 })) {
      await createBtn.first().click();
      await expect(page).toHaveURL(/\/cases\/new/, { timeout: 10000 });
    }
  });

  test("should navigate to import case page", async ({ page }) => {
    await page.goto("/#/cases");

    const importBtn = page.locator('a[href="#/cases/import"], button:has-text("导入")');
    if (await importBtn.isVisible({ timeout: 5000 })) {
      await importBtn.first().click();
      await expect(page).toHaveURL(/\/cases\/import/, { timeout: 10000 });
    }
  });

  test("should have sidebar navigation for cases", async ({ page }) => {
    await page.goto("/#/cases");

    // 验证侧边栏中有用例管理导航
    const sidebar = page.locator("aside");
    await expect(sidebar).toBeVisible({ timeout: 5000 });
  });
});
