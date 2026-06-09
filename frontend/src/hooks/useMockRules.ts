import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { mocksApi } from "@/api/mocks";
import type {
  MockRuleCreate,
  MockRuleUpdate,
  MockBatchCreate,
} from "@/types";

export function useMockRules(
  params: { url_pattern?: string; method?: string } = {}
) {
  return useQuery({
    queryKey: ["mockRules", params],
    queryFn: () => mocksApi.list(params),
  });
}

export function useMockRule(id: string | undefined) {
  return useQuery({
    queryKey: ["mockRule", id],
    queryFn: () => mocksApi.getById(id!),
    enabled: !!id,
  });
}

export function useCreateMockRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: MockRuleCreate) => mocksApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mockRules"] });
    },
  });
}

export function useCreateMockRulesBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: MockBatchCreate) => mocksApi.createBatch(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mockRules"] });
    },
  });
}

export function useUpdateMockRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string;
      payload: MockRuleUpdate;
    }) => mocksApi.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mockRules"] });
    },
  });
}

export function useDeleteMockRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => mocksApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mockRules"] });
    },
  });
}

export function useClearMockRules() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => mocksApi.clearAll(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mockRules"] });
    },
  });
}
