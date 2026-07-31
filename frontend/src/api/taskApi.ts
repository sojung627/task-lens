import axios from "axios";

import type {
  AnalyzeInstructionRequest,
  AnalyzeInstructionResponse,
} from "../types/workspace";

const configuredTimeout = Number(import.meta.env.VITE_API_TIMEOUT_MS);
const requestTimeout = Number.isFinite(configuredTimeout)
  ? configuredTimeout
  : 60_000;

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: requestTimeout,
  headers: {
    "Content-Type": "application/json",
  },
});

export async function analyzeInstruction(
  request: AnalyzeInstructionRequest,
): Promise<AnalyzeInstructionResponse> {
  const response = await apiClient.post<AnalyzeInstructionResponse>(
    "/tasks/analyze",
    request,
  );
  return response.data;
}
