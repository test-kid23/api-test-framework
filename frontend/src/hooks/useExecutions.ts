import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { executionsApi, type ExecutionListParams } from "@/api/executions";

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

export function useTriggerExecution() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      suiteId,
      envName,
    }: {
      suiteId: string;
      envName: string;
    }) => executionsApi.trigger(suiteId, envName),
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
