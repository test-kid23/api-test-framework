import client from "./client";
import type { Suite, SuiteCreate, SuiteUpdate, PaginatedResponse } from "@/types";

export interface SuiteListParams {
  page?: number;
  page_size?: number;
  search?: string;
}

export const suitesApi = {
  list: async (
    params: SuiteListParams = {}
  ): Promise<PaginatedResponse<Suite>> => {
    const { data } = await client.get("/suites", { params });
    return data;
  },

  getById: async (id: string): Promise<Suite> => {
    const { data } = await client.get(`/suites/${id}`);
    return data;
  },

  create: async (payload: SuiteCreate): Promise<Suite> => {
    const { data } = await client.post("/suites", payload);
    return data;
  },

  update: async (id: string, payload: SuiteUpdate): Promise<Suite> => {
    const { data } = await client.put(`/suites/${id}`, payload);
    return data;
  },

  delete: async (id: string): Promise<void> => {
    await client.delete(`/suites/${id}`);
  },
};
