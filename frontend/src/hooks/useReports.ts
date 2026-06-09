import { useQuery } from "@tanstack/react-query";
import { reportsApi } from "@/api/reports";

/** 合并 trends + top-failures 的 Dashboard 聚合（兼容旧版） */
export function useDashboard(days = 30) {
  return useQuery({
    queryKey: ["dashboard", days],
    queryFn: () => reportsApi.getDashboard(days),
  });
}

/** 通过率趋势（GET /reports/trends） */
export function useTrends(days = 30) {
  return useQuery({
    queryKey: ["trends", days],
    queryFn: () => reportsApi.getTrends(days),
  });
}

/** Top N 失败用例（GET /reports/top-failures） */
export function useTopFailures(limit = 10) {
  return useQuery({
    queryKey: ["topFailures", limit],
    queryFn: () => reportsApi.getTopFailures(limit),
  });
}
