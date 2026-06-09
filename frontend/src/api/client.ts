import axios from "axios";
import { useAuthStore } from "@/store/authStore";

const client = axios.create({
  baseURL: "/api/v1",
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

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

// ── 响应拦截器：解包 SuccessResponse + 处理 401 ──
client.interceptors.response.use(
  (response) => {
    // 后端统一用 SuccessResponse<T> 包裹，自动解包: { success, data } → data
    const body = response.data;
    if (body && typeof body === "object" && "success" in body && "data" in body) {
      response.data = body.data;
    }
    return response;
  },
  (error) => {
    const status = error.response?.status;

    if (status === 401) {
      // Token 过期或无效 — 清除登录状态并跳转到登录页
      useAuthStore.getState().logout();
      // 避免在登录页上重复跳转
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
