import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { environmentsApi } from "@/api/environments";
import type { EnvironmentCreate, EnvironmentUpdate } from "@/types";

export function useEnvironments(
  params: { page?: number; page_size?: number } = {}
) {
  return useQuery({
    queryKey: ["environments", params],
    queryFn: () => environmentsApi.list(params),
  });
}

export function useEnvironment(id: string | undefined) {
  return useQuery({
    queryKey: ["environment", id],
    queryFn: () => environmentsApi.getById(id!),
    enabled: !!id,
  });
}

export function useCreateEnvironment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: EnvironmentCreate) =>
      environmentsApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["environments"] });
    },
  });
}

export function useUpdateEnvironment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string;
      payload: EnvironmentUpdate;
    }) => environmentsApi.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["environments"] });
    },
  });
}

export function useDeleteEnvironment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => environmentsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["environments"] });
    },
  });
}
