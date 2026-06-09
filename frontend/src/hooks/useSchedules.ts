import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { schedulesApi, type ScheduleListParams } from "@/api/schedules";
import type { ScheduleCreate, ScheduleUpdate } from "@/types";

export function useSchedules(params: ScheduleListParams = {}) {
  return useQuery({
    queryKey: ["schedules", params],
    queryFn: () => schedulesApi.list(params),
  });
}

export function useSchedule(id: string | undefined) {
  return useQuery({
    queryKey: ["schedule", id],
    queryFn: () => schedulesApi.getById(id!),
    enabled: !!id,
  });
}

export function useCreateSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ScheduleCreate) => schedulesApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
    },
  });
}

export function useUpdateSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string;
      payload: ScheduleUpdate;
    }) => schedulesApi.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
    },
  });
}

export function useDeleteSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => schedulesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
    },
  });
}

export function useRunSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => schedulesApi.runNow(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
      queryClient.invalidateQueries({ queryKey: ["executions"] });
    },
  });
}
