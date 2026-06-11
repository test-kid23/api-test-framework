/**
 * 登录流程 E2E 测试.
 *
 * 覆盖:
 * - 正常登录流程
 * - 空字段验证
 * - 错误凭据提示
 * - 登出流程
 */
import { test, expect } from "@playwright/test";
import { login, logout, clearAuth, TEST_USERS } from "./fixtures/auth";

test.describe("Login Flow", () => {
  test.beforeEach(async ({ page }) => {
    await clearAuth(page);
  });

  test("should display login page", async ({ page }) => {
    await page.goto("/#/login");

    await expect(page.locator("#username")).toBeVisible();
    await expect(page.locator("#password")).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
    await expect(page.locator("text=AutoTest Framework")).toBeVisible();
  });

  test("should show validation error for empty fields", async ({ page }) => {
    await page.goto("/#/login");
    await page.click('button[type="submit"]');

    await expect(page.locator("text=请输入用户名和密码")).toBeVisible();
  });

  test("should show error for invalid credentials", async ({ page }) => {
    await page.goto("/#/login");

    await page.fill("#username", "nonexistent_user");
    await page.fill("#password", "wrong_password");
    await page.click('button[type="submit"]');

    // 应显示错误信息
    await expect(page.locator('[class*="destructive"]')).toBeVisible({
      timeout: 10000,
    });
  });

  test("should redirect to /login when accessing protected route without auth", async ({ page }) => {
    await page.goto("/#/cases");
    await page.waitForURL("**/login", { timeout: 10000 });

    await expect(page.locator("#username")).toBeVisible();
  });

  test("should navigate to register page from login", async ({ page }) => {
    await page.goto("/#/login");
    await page.click("text=去注册");

    await expect(page).toHaveURL(/\/register/);
  });

  test("should logout successfully", async ({ page }) => {
    await login(page, TEST_USERS.admin);

    // 验证登录成功
    await expect(page).toHaveURL(/\/cases/);

    await logout(page);

    // 验证已跳转到登录页
    await expect(page).toHaveURL(/\/login/);
  });
});
