import client from "./client";
import type {
  TestCase,
  TestCaseCreate,
  TestCaseUpdate,
  PaginatedResponse,
} from "@/types";

export interface CaseListParams {
  page?: number;
  page_size?: number;
  search?: string;
  tags?: string;
  priority?: string;
}

export const casesApi = {
  list: async (
    params: CaseListParams = {}
  ): Promise<PaginatedResponse<TestCase>> => {
    const { data } = await client.get("/cases", { params });
    return data;
  },

  getById: async (id: string): Promise<TestCase> => {
    const { data } = await client.get(`/cases/${id}`);
    return data;
  },

  create: async (payload: TestCaseCreate): Promise<TestCase> => {
    const { data } = await client.post("/cases", payload);
    return data;
  },

  update: async (
    id: string,
    payload: TestCaseUpdate
  ): Promise<TestCase> => {
    const { data } = await client.put(`/cases/${id}`, payload);
    return data;
  },

  delete: async (id: string): Promise<void> => {
    await client.delete(`/cases/${id}`);
  },

  getVersions: async (
    id: string
  ): Promise<{ version: number; created_at: string }[]> => {
    const { data } = await client.get(`/cases/${id}/versions`);
    return data;
  },
};
