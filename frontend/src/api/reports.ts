import client from "./client";
import type {
  TrendResponse,
  TopFailuresResponse,
  ReportListItem,
  PaginatedResponse,
  DashboardData,
} from "@/types";
import { analyticsApi } from "./analytics";

export interface ReportListParams {
  page?: number;
  page_size?: number;
  env_name?: string;
}

export const reportsApi = {
  list: async (
    params: ReportListParams = {}
  ): Promise<PaginatedResponse<ReportListItem>> => {
    const { data } = await client.get("/reports", { params });
    return data;
  },

  getById: async (id: string): Promise<ReportListItem> => {
    const { data } = await client.get(`/reports/${id}`);
    return data;
  },

  getTrends: async (days = 30): Promise<TrendResponse> => {
    const { data } = await client.get("/reports/trends", {
      params: { days },
    });
    return data;
  },

  getTopFailures: async (limit = 10): Promise<TopFailuresResponse> => {
    const { data } = await client.get("/reports/top-failures", {
      params: { limit },
    });
    return data;
  },

  // 兼容旧版 Dashboard 聚合（合并 trends + top-failures + failure-categories）
  getDashboard: async (days = 30): Promise<DashboardData> => {
    const [trends, failures, failureCategories] = await Promise.all([
      reportsApi.getTrends(days),
      reportsApi.getTopFailures(10),
      analyticsApi.getFailureCategories({ days }).catch(() => ({ items: [] })),
    ]);
    return {
      pass_rate_trend: trends.items.map((t) => ({
        date: t.date,
        rate: t.pass_rate,
      })),
      failure_categories: failureCategories.items.map((c) => ({
        category: c.label,
        count: c.count,
      })),
      top_unstable: failures.items.map((f) => ({
        case_name: f.case_name,
        failure_count: f.fail_count,
      })),
    };
  },
};
