import client from "./client";
import type { DashboardData } from "@/types";

export const reportsApi = {
  getDashboard: async (days = 30): Promise<DashboardData> => {
    const { data } = await client.get("/reports/dashboard", {
      params: { days },
    });
    return data;
  },
};
