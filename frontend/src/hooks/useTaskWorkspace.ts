import axios from "axios";
import { useCallback, useMemo, useState } from "react";

import { analyzeInstruction } from "../api/taskApi";
import type {
  AnalysisResult,
  ChatAttachment,
  ChatMessage,
  ConversationSummary,
  WorkspaceSnapshot,
} from "../types/workspace";

const emptyWorkspace: WorkspaceSnapshot = {
  conversations: [],
  recentFiles: [],
  activeConversationId: null,
  messages: [],
  analysis: null,
};

function nowLabel(): string {
  return new Intl.DateTimeFormat("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date());
}

function createId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

function getErrorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) {
    return "예상하지 못한 오류가 발생했어요.";
  }

  if (!error.response) {
    return "백엔드에 연결할 수 없어요. 서버 실행 상태를 확인해 주세요.";
  }

  const detail = error.response.data?.detail;
  if (typeof detail === "string") {
    return detail;
  }

  if (error.response.status === 422) {
    return "입력 내용을 확인해 주세요.";
  }
  if (error.response.status === 429) {
    return "AI 호출 한도를 초과했어요. 잠시 후 다시 시도해 주세요.";
  }
  if (error.response.status === 504) {
    return "AI 응답 시간이 1분을 초과했어요.";
  }
  return "분석 요청에 실패했어요. 백엔드 터미널 로그를 확인해 주세요.";
}

export function useTaskWorkspace() {
  const [workspace, setWorkspace] = useState<WorkspaceSnapshot>(emptyWorkspace);
  const [message, setMessage] = useState("");
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const activeConversation = useMemo(
    () =>
      workspace.conversations.find(
        (conversation) => conversation.id === workspace.activeConversationId,
      ) ?? null,
    [workspace.activeConversationId, workspace.conversations],
  );

  const selectConversation = useCallback((_conversationId: string) => {
    setErrorMessage("대화 저장 기능은 핵심 분석 기능 완성 후 추가할 예정이에요.");
  }, []);

  const startConversation = useCallback(() => {
    setWorkspace(emptyWorkspace);
    setMessage("");
    setAttachments([]);
    setErrorMessage(null);
  }, []);

  const submitMessage = useCallback(async () => {
    const trimmedMessage = message.trim();
    if (!trimmedMessage) {
      setErrorMessage("업무 지시를 입력해 주세요.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const response = await analyzeInstruction({ message: trimmedMessage });
      const conversationId = workspace.activeConversationId ?? createId("conversation");
      const createdAt = nowLabel();
      const userMessage: ChatMessage = {
        id: createId("message"),
        role: "user",
        content: trimmedMessage,
        createdAt,
        attachments,
      };
      const assistantMessage: ChatMessage = {
        id: createId("message"),
        role: "assistant",
        content: `업무 ${response.analysis.tasks.length}개를 구조화했어요.`,
        createdAt,
        attachments: [],
      };
      const conversation: ConversationSummary = {
        id: conversationId,
        title: response.analysis.core_goal,
        preview: trimmedMessage.slice(0, 38),
        updatedAt: createdAt,
      };

      setWorkspace((current) => ({
        ...current,
        activeConversationId: conversationId,
        conversations: [
          conversation,
          ...current.conversations.filter((item) => item.id !== conversationId),
        ],
        messages: [...current.messages, userMessage, assistantMessage],
        analysis: response.analysis,
      }));
      setMessage("");
      setAttachments([]);
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }, [attachments, message, workspace.activeConversationId]);

  const toggleChecklist = useCallback(
    (itemId: string, completed: boolean) => {
      setWorkspace((current) => {
        if (!current.analysis) {
          return current;
        }

        const analysis: AnalysisResult = {
          ...current.analysis,
          tasks: current.analysis.tasks.map((task) =>
            task.id === itemId ? { ...task, completed } : task,
          ),
        };
        return { ...current, analysis };
      });
    },
    [],
  );

  return {
    workspace,
    activeConversation,
    message,
    attachments,
    isLoading: false,
    isSubmitting,
    errorMessage,
    setMessage,
    setAttachments,
    selectConversation,
    startConversation,
    submitMessage,
    toggleChecklist,
  };
}
