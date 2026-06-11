/**
 * E2E 测试认证辅助工具.
 *
 * 提供登录/登出/注册等常用认证操作的 Playwright 封装。
 */
import { type Page } from "@playwright/test";

export interface TestUser {
  username: string;
  password: string;
}

export const TEST_USERS = {
  admin: { username: "admin", password: "Admin@123456" },
  editor: { username: "editor", password: "Editor@123456" },
} as const satisfies Record<string, TestUser>;

/**
 * 通过 UI 执行登录操作.
 */
export async function login(page: Page, user: TestUser): Promise<void> {
  await page.goto("/#/login");
  await page.waitForSelector("#username");

  await page.fill("#username", user.username);
  await page.fill("#password", user.password);
  await page.click('button[type="submit"]');

  // 等待导航到 /cases 页面
  await page.waitForURL("**/cases", { timeout: 15000 });
}

/**
 * 通过 UI 执行登出操作.
 */
export async function logout(page: Page): Promise<void> {
  // 点击用户头像/菜单按钮
  const avatarBtn = page.locator('[data-testid="user-menu-trigger"]');
  if (await avatarBtn.isVisible()) {
    await avatarBtn.click();
  } else {
    // fallback: 点击 header 中的任何按钮触发菜单
    const headerBtns = page.locator("header button");
    const count = await headerBtns.count();
    if (count > 0) {
      await headerBtns.last().click();
    }
  }

  // 点击退出登录
  const logoutBtn = page.locator('text=退出登录');
  if (await logoutBtn.isVisible({ timeout: 3000 })) {
    await logoutBtn.click();
  }

  // 等待跳转到登录页
  await page.waitForURL("**/login", { timeout: 10000 });
}

/**
 * 清除 localStorage 中的认证信息.
 */
export async function clearAuth(page: Page): Promise<void> {
  await page.evaluate(() => {
    localStorage.removeItem("autotest-token");
    localStorage.removeItem("autotest-refresh-token");
    localStorage.removeItem("autotest-user");
  });
}
