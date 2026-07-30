import axios from "axios";

import type {
  AnalysisResult,
  AnalyzeInstructionRequest,
  AnalyzeInstructionResponse,
  ConversationId,
  WorkspaceSnapshot,
} from "../types/workspace";

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api",
  timeout: 30_000,
  headers: {
    "Content-Type": "application/json",
  },
});

export async function fetchWorkspace(): Promise<WorkspaceSnapshot> {
  const response = await apiClient.get<WorkspaceSnapshot>("/workspace");
  return response.data;
}

export async function fetchConversation(
  conversationId: ConversationId,
): Promise<WorkspaceSnapshot> {
  const response = await apiClient.get<WorkspaceSnapshot>(
    `/conversations/${conversationId}`,
  );
  return response.data;
}

export async function analyzeInstruction(
  request: AnalyzeInstructionRequest,
): Promise<AnalyzeInstructionResponse> {
  const response = await apiClient.post<AnalyzeInstructionResponse>(
    "/tasks/analyze",
    request,
  );
  return response.data;
}

export async function updateChecklistItem(
  itemId: string,
  completed: boolean,
): Promise<AnalysisResult> {
  const response = await apiClient.patch<AnalysisResult>(
    `/checklist/${itemId}`,
    { completed },
  );
  return response.data;
}

export async function createConversation(): Promise<WorkspaceSnapshot> {
  const response = await apiClient.post<WorkspaceSnapshot>("/conversations");
  return response.data;
}
