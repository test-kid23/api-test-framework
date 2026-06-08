import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { casesApi, type CaseListParams } from "@/api/cases";
import type { TestCaseCreate, TestCaseUpdate } from "@/types";

export function useCases(params: CaseListParams = {}) {
  return useQuery({
    queryKey: ["cases", params],
    queryFn: () => casesApi.list(params),
  });
}

export function useCase(id: string | undefined) {
  return useQuery({
    queryKey: ["case", id],
    queryFn: () => casesApi.getById(id!),
    enabled: !!id,
  });
}

export function useCreateCase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TestCaseCreate) => casesApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cases"] });
    },
  });
}

export function useUpdateCase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: TestCaseUpdate }) =>
      casesApi.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cases"] });
    },
  });
}

export function useDeleteCase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => casesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cases"] });
    },
  });
}
