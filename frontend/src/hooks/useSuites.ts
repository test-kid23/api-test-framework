import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { suitesApi, type SuiteListParams } from "@/api/suites";
import type { SuiteCreate, SuiteUpdate } from "@/types";

export function useSuites(params: SuiteListParams = {}) {
  return useQuery({
    queryKey: ["suites", params],
    queryFn: () => suitesApi.list(params),
  });
}

export function useSuite(id: string | undefined) {
  return useQuery({
    queryKey: ["suite", id],
    queryFn: () => suitesApi.getById(id!),
    enabled: !!id,
  });
}

export function useCreateSuite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SuiteCreate) => suitesApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["suites"] });
    },
  });
}

export function useUpdateSuite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: SuiteUpdate }) =>
      suitesApi.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["suites"] });
    },
  });
}

export function useDeleteSuite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => suitesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["suites"] });
    },
  });
}
