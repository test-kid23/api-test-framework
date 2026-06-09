import client from "./client";
import type {
  Execution,
  ExecutionRequest,
  ExecutionReport,
  PaginatedResponse,
} from "@/types";

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

  getById: async (id: string): Promise<Execution> => {
    const { data } = await client.get(`/executions/${id}`);
    return data;
  },

  getStatus: async (
    id: string
  ): Promise<{ status: string; progress?: number }> => {
    const { data } = await client.get(`/executions/${id}/status`);
    return data;
  },

  getReport: async (id: string): Promise<ExecutionReport> => {
    const { data } = await client.get(`/executions/${id}/report`);
    return data;
  },

  trigger: async (payload: ExecutionRequest): Promise<Execution> => {
    const { data } = await client.post("/executions", payload);
    return data;
  },

  cancel: async (id: string): Promise<void> => {
    await client.post(`/executions/${id}/cancel`);
  },
};
