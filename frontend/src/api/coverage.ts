import client from "./client";
import type {
  CoverageReport,
  CoverageAnalysisRequest,
  CoverageGenerateRequest,
  GenerateResultResponse,
} from "@/types";

export const coverageApi = {
  analyze: async (payload: CoverageAnalysisRequest): Promise<CoverageReport> => {
    const { data } = await client.post("/coverage/analyze", payload);
    return data;
  },

  generate: async (payload: CoverageGenerateRequest): Promise<GenerateResultResponse> => {
    const { data } = await client.post("/coverage/generate", payload);
    return data;
  },

  generateAndSave: async (payload: CoverageGenerateRequest): Promise<GenerateResultResponse> => {
    const { data } = await client.post("/coverage/generate-and-save", payload);
    return data;
  },
};
