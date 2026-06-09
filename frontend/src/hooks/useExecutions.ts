import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { executionsApi, type ExecutionListParams } from "@/api/executions";
import type { ExecutionRequest } from "@/types";

export function useExecutions(params: ExecutionListParams = {}) {
  return useQuery({
    queryKey: ["executions", params],
    queryFn: () => executionsApi.list(params),
    refetchInterval: 10000,
  });
}

export function useExecution(id: string | undefined) {
  return useQuery({
    queryKey: ["execution", id],
    queryFn: () => executionsApi.getById(id!),
    enabled: !!id,
  });
}

export function useExecutionStatus(id: string | undefined) {
  return useQuery({
    queryKey: ["executionStatus", id],
    queryFn: () => executionsApi.getStatus(id!),
    enabled: !!id,
    refetchInterval: 3000,
  });
}

export function useExecutionReport(id: string | undefined) {
  return useQuery({
    queryKey: ["executionReport", id],
    queryFn: () => executionsApi.getReport(id!),
    enabled: !!id,
  });
}

export function useTriggerExecution() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ExecutionRequest) => executionsApi.trigger(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["executions"] });
    },
  });
}

export function useCancelExecution() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => executionsApi.cancel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["executions"] });
    },
  });
}
