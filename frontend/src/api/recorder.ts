import client from "./client";
import type {
  RecorderStatus,
  RecordingSession,
  StartRecordingRequest,
  ReplayRequest,
  PlaybackReport,
  GenerateRequest,
  GenerateResult,
} from "@/types";

export const recorderApi = {
  start: async (payload: StartRecordingRequest): Promise<{ session_id: string; message: string }> => {
    const { data } = await client.post("/recorder/start", payload);
    return data;
  },

  stop: async (saveDir?: string): Promise<{ har_file: string; message: string }> => {
    const { data } = await client.post("/recorder/stop", { save_dir: saveDir });
    return data;
  },

  pause: async (): Promise<{ message: string }> => {
    const { data } = await client.post("/recorder/pause");
    return data;
  },

  resume: async (): Promise<{ message: string }> => {
    const { data } = await client.post("/recorder/resume");
    return data;
  },

  getStatus: async (): Promise<RecorderStatus> => {
    const { data } = await client.get("/recorder/status");
    return data;
  },

  listSessions: async (): Promise<RecordingSession[]> => {
    const { data } = await client.get("/recorder/sessions");
    return data;
  },

  getSession: async (sessionId: string): Promise<RecordingSession> => {
    const { data } = await client.get(`/recorder/sessions/${sessionId}`);
    return data;
  },

  replaySession: async (
    sessionId: string,
    payload: ReplayRequest
  ): Promise<PlaybackReport> => {
    const { data } = await client.post(
      `/recorder/sessions/${sessionId}/replay`,
      payload
    );
    return data;
  },

  replayHar: async (payload: ReplayRequest): Promise<PlaybackReport> => {
    const { data } = await client.post("/recorder/replay", payload);
    return data;
  },

  generateCases: async (payload: GenerateRequest): Promise<GenerateResult> => {
    const { data } = await client.post("/recorder/generate", payload);
    return data;
  },

  getHarContent: async (sessionId: string): Promise<unknown> => {
    const { data } = await client.get(`/recorder/har/${sessionId}`);
    return data;
  },
};
