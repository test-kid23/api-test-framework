import client from "./client";
import type {
  Schedule,
  ScheduleCreate,
  ScheduleUpdate,
  PaginatedResponse,
} from "@/types";

export interface ScheduleListParams {
  page?: number;
  page_size?: number;
}

export const schedulesApi = {
  list: async (
    params: ScheduleListParams = {}
  ): Promise<PaginatedResponse<Schedule>> => {
    const { data } = await client.get("/schedules", { params });
    return data;
  },

  getById: async (id: string): Promise<Schedule> => {
    const { data } = await client.get(`/schedules/${id}`);
    return data;
  },

  create: async (payload: ScheduleCreate): Promise<Schedule> => {
    const { data } = await client.post("/schedules", payload);
    return data;
  },

  update: async (id: string, payload: ScheduleUpdate): Promise<Schedule> => {
    const { data } = await client.put(`/schedules/${id}`, payload);
    return data;
  },

  delete: async (id: string): Promise<void> => {
    await client.delete(`/schedules/${id}`);
  },

  runNow: async (id: string): Promise<Schedule> => {
    const { data } = await client.post(`/schedules/${id}/run`);
    return data;
  },
};
