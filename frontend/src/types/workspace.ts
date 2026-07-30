export type ConversationId = string;

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

export interface ChecklistItem {
  id: string;
  content: string;
  completed: boolean;
  dueLabel?: string;
}

export interface DifficultTerm {
  term: string;
  explanation: string;
}

export interface AnalysisResult {
  summary: string[];
  checklist: ChecklistItem[];
  nextStep?: string;
  deadline?: string;
  confirmationItems: string[];
  difficultTerms: DifficultTerm[];
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
  conversationId?: ConversationId;
  message: string;
  attachmentIds: string[];
}

export interface AnalyzeInstructionResponse {
  conversationId: ConversationId;
  userMessage: ChatMessage;
  assistantMessage: ChatMessage;
  analysis: AnalysisResult;
  conversation: ConversationSummary;
}
