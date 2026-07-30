import { useCallback, useEffect, useMemo, useState } from "react";

import {
  analyzeInstruction,
  createConversation,
  fetchConversation,
  fetchWorkspace,
  updateChecklistItem,
} from "../api/taskApi";
import type {
  AnalysisResult,
  ChatAttachment,
  WorkspaceSnapshot,
} from "../types/workspace";

const emptyWorkspace: WorkspaceSnapshot = {
  conversations: [],
  recentFiles: [],
  activeConversationId: null,
  messages: [],
  analysis: null,
};

export function useTaskWorkspace() {
  const [workspace, setWorkspace] = useState<WorkspaceSnapshot>(emptyWorkspace);
  const [message, setMessage] = useState("");
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadWorkspace = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      setWorkspace(await fetchWorkspace());
    } catch {
      setWorkspace(emptyWorkspace);
      setErrorMessage("백엔드 연결 후 대화와 분석 결과가 표시돼요.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  const activeConversation = useMemo(
    () =>
      workspace.conversations.find(
        (conversation) => conversation.id === workspace.activeConversationId,
      ) ?? null,
    [workspace.activeConversationId, workspace.conversations],
  );

  const selectConversation = useCallback(async (conversationId: string) => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      setWorkspace(await fetchConversation(conversationId));
    } catch {
      setErrorMessage("대화 내용을 불러오지 못했어요.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const startConversation = useCallback(async () => {
    setErrorMessage(null);

    try {
      setWorkspace(await createConversation());
      setMessage("");
      setAttachments([]);
    } catch {
      setWorkspace((current) => ({
        ...current,
        activeConversationId: null,
        messages: [],
        analysis: null,
      }));
    }
  }, []);

  const submitMessage = useCallback(async () => {
    const trimmedMessage = message.trim();

    if (!trimmedMessage && attachments.length === 0) {
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const response = await analyzeInstruction({
        conversationId: workspace.activeConversationId ?? undefined,
        message: trimmedMessage,
        attachmentIds: attachments.map((attachment) => attachment.id),
      });

      setWorkspace((current) => ({
        ...current,
        activeConversationId: response.conversationId,
        conversations: [
          response.conversation,
          ...current.conversations.filter(
            (conversation) => conversation.id !== response.conversationId,
          ),
        ],
        messages: [
          ...current.messages,
          response.userMessage,
          response.assistantMessage,
        ],
        analysis: response.analysis,
      }));
      setMessage("");
      setAttachments([]);
    } catch {
      setErrorMessage("분석 요청에 실패했어요. 백엔드 실행 상태를 확인해 주세요.");
    } finally {
      setIsSubmitting(false);
    }
  }, [attachments, message, workspace.activeConversationId]);

  const toggleChecklist = useCallback(
    async (itemId: string, completed: boolean) => {
      const previousAnalysis = workspace.analysis;

      if (!previousAnalysis) {
        return;
      }

      const optimisticAnalysis: AnalysisResult = {
        ...previousAnalysis,
        checklist: previousAnalysis.checklist.map((item) =>
          item.id === itemId ? { ...item, completed } : item,
        ),
      };

      setWorkspace((current) => ({ ...current, analysis: optimisticAnalysis }));

      try {
        const updatedAnalysis = await updateChecklistItem(itemId, completed);
        setWorkspace((current) => ({ ...current, analysis: updatedAnalysis }));
      } catch {
        setWorkspace((current) => ({ ...current, analysis: previousAnalysis }));
        setErrorMessage("체크 상태를 저장하지 못했어요.");
      }
    },
    [workspace.analysis],
  );

  return {
    workspace,
    activeConversation,
    message,
    attachments,
    isLoading,
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
