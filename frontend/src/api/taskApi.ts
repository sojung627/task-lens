import axios from "axios";

import type {
  AnalysisResult,
  ChatRequest,
  ChatResponse,
  ReminderSummary,
  TaskUpdatePayload,
  WorkspaceSnapshot,
} from "../types/workspace";

const configuredTimeout = Number(import.meta.env.VITE_API_TIMEOUT_MS);
const requestTimeout = Number.isFinite(configuredTimeout) ? configuredTimeout : 60_000;
const apiBaseUrl = String(import.meta.env.VITE_API_BASE_URL || "/api");

const apiClient = axios.create({
  baseURL: apiBaseUrl,
  timeout: requestTimeout,
  headers: { "Content-Type": "application/json" },
});

function normalizeWorkspace(data: Partial<WorkspaceSnapshot> | null | undefined): WorkspaceSnapshot {
  return {
    conversations: Array.isArray(data?.conversations) ? data.conversations : [],
    trashedConversations: Array.isArray(data?.trashedConversations)
      ? data.trashedConversations
      : [],
    recentFiles: Array.isArray(data?.recentFiles) ? data.recentFiles : [],
    sourceFiles: Array.isArray(data?.sourceFiles) ? data.sourceFiles : [],
    activeConversationId:
      typeof data?.activeConversationId === "string" ? data.activeConversationId : null,
    messages: Array.isArray(data?.messages) ? data.messages : [],
    analysis: data?.analysis ?? null,
    notes: typeof data?.notes === "string" ? data.notes : "",
    reminders: Array.isArray(data?.reminders) ? data.reminders : [],
  };
}

export async function getWorkspace(conversationId?: string): Promise<WorkspaceSnapshot> {
  const response = await apiClient.get<WorkspaceSnapshot>("/workspace", {
    params: conversationId ? { conversation_id: conversationId } : undefined,
  });
  return normalizeWorkspace(response.data);
}

export async function sendChat(request: ChatRequest): Promise<ChatResponse> {
  const response = await apiClient.post<ChatResponse>("/chat", request);
  return response.data;
}

export async function transcribeAudio(request: {
  name: string;
  mime_type: string;
  content_base64: string;
  language?: string;
}): Promise<string> {
  const response = await apiClient.post<{ text: string }>("/audio/transcribe", {
    ...request,
    language: request.language ?? "ko",
  });
  return response.data.text;
}

export async function renameConversation(conversationId: string, title: string): Promise<void> {
  await apiClient.patch(`/conversations/${conversationId}`, { title });
}

export async function trashConversation(conversationId: string): Promise<void> {
  await apiClient.delete(`/conversations/${conversationId}`);
}

export async function restoreConversation(conversationId: string): Promise<void> {
  await apiClient.post(`/conversations/${conversationId}/restore`);
}

export async function deleteConversationPermanently(conversationId: string): Promise<void> {
  await apiClient.delete(`/conversations/${conversationId}/permanent`);
}

export async function saveNotes(conversationId: string, content: string): Promise<void> {
  await apiClient.put(`/conversations/${conversationId}/notes`, { content });
}

export async function updateTask(
  conversationId: string,
  taskId: string,
  changes: TaskUpdatePayload,
): Promise<AnalysisResult> {
  const response = await apiClient.patch<{ analysis: AnalysisResult }>(
    `/conversations/${conversationId}/tasks/${taskId}`,
    changes,
  );
  return response.data.analysis;
}

export async function deleteTask(
  conversationId: string,
  taskId: string,
): Promise<AnalysisResult> {
  const response = await apiClient.delete<{ analysis: AnalysisResult }>(
    `/conversations/${conversationId}/tasks/${taskId}`,
  );
  return response.data.analysis;
}

export async function createReminder(request: {
  conversationId: string;
  taskId?: string;
  message: string;
  remindAt: string;
}): Promise<ReminderSummary> {
  const response = await apiClient.post<ReminderSummary>(
    `/conversations/${request.conversationId}/reminders`,
    {
      task_id: request.taskId ?? null,
      message: request.message,
      remind_at: request.remindAt,
    },
  );
  return response.data;
}

export async function getDueReminders(): Promise<ReminderSummary[]> {
  const response = await apiClient.get<ReminderSummary[]>("/reminders/due");
  return Array.isArray(response.data) ? response.data : [];
}

export async function updateReminderStatus(
  reminderId: string,
  status: ReminderSummary["status"],
): Promise<void> {
  await apiClient.patch(`/reminders/${reminderId}`, { status });
}

export function resolveDownloadUrl(downloadUrl: string): string {
  if (/^https?:\/\//.test(downloadUrl)) {
    return downloadUrl;
  }
  const normalizedBase = apiBaseUrl.replace(/\/$/, "");
  const normalizedPath = downloadUrl.replace(/^\/api/, "");
  return `${normalizedBase}${normalizedPath}`;
}