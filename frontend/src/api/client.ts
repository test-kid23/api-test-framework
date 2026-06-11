import axios from "axios";
import { useAuthStore } from "@/store/authStore";

const client = axios.create({
  baseURL: "/api/v1",
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

// ── 刷新 token 的防并发锁 ──
let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

function subscribeTokenRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb);
}

function onTokenRefreshed(newToken: string) {
  refreshSubscribers.forEach((cb) => cb(newToken));
  refreshSubscribers = [];
}

// ── 请求拦截器：自动附加 Bearer Token ──
client.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// ── 响应拦截器：解包 SuccessResponse + 静默刷新 401 ──
client.interceptors.response.use(
  (response) => {
    // 后端统一用 SuccessResponse<T> 包裹，自动解包: { success, data } → data
    const body = response.data;
    if (body && typeof body === "object" && "success" in body && "data" in body) {
      response.data = body.data;
    }
    return response;
  },
  async (error) => {
    const originalRequest = error.config;
    const status = error.response?.status;

    if (status === 401 && !originalRequest._retry) {
      const store = useAuthStore.getState();
      const refreshToken = store.refreshToken;

      // 有 refresh token 时尝试静默刷新
      if (refreshToken) {
        if (isRefreshing) {
          // 已有刷新请求在进行中，排队等待
          return new Promise((resolve) => {
            subscribeTokenRefresh((newToken: string) => {
              originalRequest.headers.Authorization = `Bearer ${newToken}`;
              originalRequest._retry = true;
              resolve(client(originalRequest));
            });
          });
        }

        originalRequest._retry = true;
        isRefreshing = true;

        try {
          const response = await axios.post("/api/v1/auth/refresh", {
            refresh_token: refreshToken,
          });
          const newToken = response.data?.data?.access_token;
          if (newToken) {
            store.setToken(newToken);
            onTokenRefreshed(newToken);
            isRefreshing = false;
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
            return client(originalRequest);
          }
        } catch {
          // 刷新失败，清除状态并跳转登录
          isRefreshing = false;
          refreshSubscribers = [];
        }
      }

      // 刷新失败或无 refresh token — 清除登录状态并跳转
      store.logout();
      if (window.location.hash !== "#/login") {
        window.location.hash = "#/login";
      }
    }

    const message =
      error.response?.data?.detail || error.response?.data?.error || error.message || "请求失败";

    // 提取后端结构化错误消息
    let displayMessage = message;
    if (typeof message === "object") {
      if (message.msg) displayMessage = message.msg;
      else if (message.error) displayMessage = message.error;
      else if (Array.isArray(message)) {
        displayMessage = message.map((e: { msg?: string }) => e.msg || "").join("; ");
      }
    }

    console.error(`[API Error ${status}] ${displayMessage}`);
    return Promise.reject(error);
  },
);

export default client;
