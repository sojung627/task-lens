export type ConversationId = string;
export type Priority = "urgent" | "high" | "normal" | "low" | "unspecified";

export interface ConversationSummary {
  id: ConversationId;
  title: string;
  updatedAt: string;
  preview?: string;
}

export interface SourceFile {
  id: string;
  name: string;
  extension: string;
  uploadedAt: string;
  sizeLabel?: string;
}

export type MessageRole = "user" | "assistant";

export interface ChatAttachment {
  id: string;
  name: string;
  extension: string;
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
  completed?: boolean;
}

export interface DifficultTerm {
  term: string;
  explanation: string;
}

export interface AnalysisResult {
  core_goal: string;
  tasks: TaskItem[];
  confirmation_items: string[];
  difficult_terms: DifficultTerm[];
  ambiguities: string[];
}

export interface WorkspaceSnapshot {
  conversations: ConversationSummary[];
  recentFiles: SourceFile[];
  activeConversationId: ConversationId | null;
  messages: ChatMessage[];
  analysis: AnalysisResult | null;
}

export interface AnalyzeInstructionRequest {
  message: string;
}

export interface AnalyzeInstructionResponse {
  request_id: string;
  model: string;
  analysis: AnalysisResult;
}
