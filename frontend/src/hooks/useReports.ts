import { useQuery } from "@tanstack/react-query";
import { reportsApi } from "@/api/reports";

export function useDashboard(days = 30) {
  return useQuery({
    queryKey: ["dashboard", days],
    queryFn: () => reportsApi.getDashboard(days),
  });
}
