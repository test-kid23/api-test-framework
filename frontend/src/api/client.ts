import axios from "axios";

const client = axios.create({
  baseURL: "/api/v1",
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

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
    const message =
      error.response?.data?.detail || error.message || "请求失败";
    console.error(`[API Error] ${message}`, error.response?.status);
    return Promise.reject(error);
  }
);

export default client;
