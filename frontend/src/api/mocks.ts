import client from "./client";
import type {
  MockRule,
  MockRuleCreate,
  MockRuleUpdate,
  MockRulesList,
  MockBatchCreate,
} from "@/types";

export const mocksApi = {
  list: async (
    params: { url_pattern?: string; method?: string } = {}
  ): Promise<MockRulesList> => {
    const { data } = await client.get("/mocks/rules", { params });
    return data;
  },

  getById: async (id: string): Promise<MockRule> => {
    const { data } = await client.get(`/mocks/rules/${id}`);
    return data;
  },

  create: async (payload: MockRuleCreate): Promise<MockRule> => {
    const { data } = await client.post("/mocks/rules", payload);
    return data;
  },

  createBatch: async (payload: MockBatchCreate): Promise<MockRule[]> => {
    const { data } = await client.post("/mocks/rules/batch", payload);
    return data;
  },

  update: async (
    id: string,
    payload: MockRuleUpdate
  ): Promise<MockRule> => {
    const { data } = await client.put(`/mocks/rules/${id}`, payload);
    return data;
  },

  delete: async (id: string): Promise<{ message: string }> => {
    const { data } = await client.delete(`/mocks/rules/${id}`);
    return data;
  },

  clearAll: async (): Promise<{ message: string }> => {
    const { data } = await client.delete("/mocks/rules");
    return data;
  },

  getStatus: async (): Promise<{ status: string; total_rules: number; enabled_rules: number; rules: MockRule[] }> => {
    const { data } = await client.get("/mocks/status");
    return data;
  },
};
