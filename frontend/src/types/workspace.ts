export type ConversationId = string;
export type Priority = "urgent" | "high" | "normal" | "low" | "unspecified";
export type TaskStatus = "todo" | "in_progress" | "done";

export interface ConversationSummary {
  id: ConversationId;
  title: string;
  updatedAt: string;
  preview?: string | null;
  status?: "active" | "trashed";
}

export interface SourceFile {
  id: string;
  name: string;
  extension: string;
  uploadedAt: string;
  sizeLabel: string;
  downloadUrl: string;
  generatedBy: "user" | "assistant";
}

export interface PendingFile {
  id: string;
  name: string;
  extension: string;
  mimeType: string;
  contentBase64: string;
  sizeLabel: string;
}

export type MessageRole = "user" | "assistant";

export interface ChatAttachment {
  id: string;
  name: string;
  extension: string;
  downloadUrl: string;
  generatedBy: "user" | "assistant";
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: string;
  attachments: ChatAttachment[];
}

export interface TaskItem {
  id: string;
  title: string;
  description: string | null;
  order: number;
  priority: Priority;
  deadline: string | null;
  assignee: string | null;
  submission_target: string | null;
  dependencies: string[];
  completion_condition: string | null;
  status: TaskStatus;
  completed: boolean;
}

export interface DifficultTerm {
  term: string;
  explanation: string;
}

export interface AnalysisResult {
  summary: string | null;
  core_goal: string;
  key_points: string[];
  decisions: string[];
  tasks: TaskItem[];
  confirmation_items: string[];
  difficult_terms: DifficultTerm[];
  ambiguities: string[];
}

export interface ReminderSummary {
  id: string;
  conversationId: string;
  taskId: string | null;
  message: string;
  remindAt: string;
  status: "pending" | "delivered" | "dismissed";
}

export interface WorkspaceSnapshot {
  conversations: ConversationSummary[];
  trashedConversations: ConversationSummary[];
  recentFiles: SourceFile[];
  sourceFiles: SourceFile[];
  activeConversationId: ConversationId | null;
  messages: ChatMessage[];
  analysis: AnalysisResult | null;
  notes: string;
  reminders: ReminderSummary[];
}

export interface TaskUpdatePayload {
  title?: string;
  description?: string | null;
  priority?: Priority;
  deadline?: string | null;
  assignee?: string | null;
  submission_target?: string | null;
  completion_condition?: string | null;
  status?: TaskStatus;
}

export interface ChatRequest {
  conversation_id: string | null;
  message: string;
  files: Array<{
    name: string;
    mime_type: string;
    content_base64: string;
  }>;
}

export interface ChatResponse {
  conversation_id: string;
  message: ChatMessage;
  analysis: AnalysisResult | null;
}