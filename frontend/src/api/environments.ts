import client from "./client";
import type {
  Environment,
  EnvironmentCreate,
  EnvironmentUpdate,
  PaginatedResponse,
} from "@/types";

export const environmentsApi = {
  list: async (
    params: { page?: number; page_size?: number } = {}
  ): Promise<PaginatedResponse<Environment>> => {
    const { data } = await client.get("/environments", { params });
    return data;
  },

  getById: async (id: string): Promise<Environment> => {
    const { data } = await client.get(`/environments/${id}`);
    return data;
  },

  create: async (payload: EnvironmentCreate): Promise<Environment> => {
    const { data } = await client.post("/environments", payload);
    return data;
  },

  update: async (
    id: string,
    payload: EnvironmentUpdate
  ): Promise<Environment> => {
    const { data } = await client.put(`/environments/${id}`, payload);
    return data;
  },

  delete: async (id: string): Promise<void> => {
    await client.delete(`/environments/${id}`);
  },
};
