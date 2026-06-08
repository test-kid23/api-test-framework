import client from "./client";
import type { Execution, ExecutionDetail, PaginatedResponse } from "@/types";

export interface ExecutionListParams {
  page?: number;
  page_size?: number;
  status?: string;
}

export const executionsApi = {
  list: async (
    params: ExecutionListParams = {}
  ): Promise<PaginatedResponse<Execution>> => {
    const { data } = await client.get("/executions", { params });
    return data;
  },

  getById: async (id: string): Promise<ExecutionDetail> => {
    const { data } = await client.get(`/executions/${id}`);
    return data;
  },

  trigger: async (suiteId: string, envName: string): Promise<Execution> => {
    const { data } = await client.post("/executions", {
      suite_id: suiteId,
      env_name: envName,
    });
    return data;
  },

  cancel: async (id: string): Promise<void> => {
    await client.post(`/executions/${id}/cancel`);
  },
};
