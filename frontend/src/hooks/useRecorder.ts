import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { recorderApi } from "@/api/recorder";
import type {
  StartRecordingRequest,
  ReplayRequest,
  GenerateRequest,
} from "@/types";

export function useRecorderStatus() {
  return useQuery({
    queryKey: ["recorderStatus"],
    queryFn: () => recorderApi.getStatus(),
    refetchInterval: 3000,
  });
}

export function useRecorderSessions() {
  return useQuery({
    queryKey: ["recorderSessions"],
    queryFn: () => recorderApi.listSessions(),
  });
}

export function useRecorderSession(sessionId: string | undefined) {
  return useQuery({
    queryKey: ["recorderSession", sessionId],
    queryFn: () => recorderApi.getSession(sessionId!),
    enabled: !!sessionId,
  });
}

export function useStartRecording() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: StartRecordingRequest) => recorderApi.start(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recorderStatus"] });
    },
  });
}

export function useStopRecording() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (saveDir?: string) => recorderApi.stop(saveDir),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recorderStatus"] });
      queryClient.invalidateQueries({ queryKey: ["recorderSessions"] });
    },
  });
}

export function usePauseRecording() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => recorderApi.pause(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recorderStatus"] });
    },
  });
}

export function useResumeRecording() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => recorderApi.resume(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recorderStatus"] });
    },
  });
}

export function useReplayHar() {
  return useMutation({
    mutationFn: (payload: ReplayRequest) => recorderApi.replayHar(payload),
  });
}

export function useReplaySession() {
  return useMutation({
    mutationFn: ({
      sessionId,
      payload,
    }: {
      sessionId: string;
      payload: ReplayRequest;
    }) => recorderApi.replaySession(sessionId, payload),
  });
}

export function useGenerateCases() {
  return useMutation({
    mutationFn: (payload: GenerateRequest) => recorderApi.generateCases(payload),
  });
}
