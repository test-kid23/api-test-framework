import client from "./client";
import type {
  StabilityRankingResponse,
  PercentileResponse,
  FailureCategoryResponse,
  RoiStatsItem,
} from "@/types";

export interface AnalyticsParams {
  days?: number;
  suite_id?: string;
  limit?: number;
}

export const analyticsApi = {
  /** 接口稳定性排行（按失败率降序） */
  getStabilityRanking: async (
    params: AnalyticsParams = {}
  ): Promise<StabilityRankingResponse> => {
    const { data } = await client.get("/analytics/stability-ranking", { params });
    return data;
  },

  /** 响应时间分位数 P50/P95/P99 */
  getPercentiles: async (
    params: Omit<AnalyticsParams, "limit"> = {}
  ): Promise<PercentileResponse> => {
    const { data } = await client.get("/analytics/percentiles", { params });
    return data;
  },

  /** 失败原因分类统计 */
  getFailureCategories: async (
    params: Omit<AnalyticsParams, "limit"> = {}
  ): Promise<FailureCategoryResponse> => {
    const { data } = await client.get("/analytics/failure-categories", { params });
    return data;
  },

  /** ROI 统计（自动化覆盖率、节省工时等） */
  getRoi: async (): Promise<RoiStatsItem> => {
    const { data } = await client.get("/analytics/roi");
    return data;
  },
};
