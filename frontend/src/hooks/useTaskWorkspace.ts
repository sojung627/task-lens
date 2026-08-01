import axios from "axios";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  createReminder,
  deleteConversationPermanently,
  deleteTask,
  getDueReminders,
  getWorkspace,
  renameConversation,
  restoreConversation,
  saveNotes,
  sendChat,
  transcribeAudio,
  trashConversation,
  updateReminderStatus,
  updateTask,
} from "../api/taskApi";
import type {
  PendingFile,
  ReminderSummary,
  TaskUpdatePayload,
  WorkspaceSnapshot,
} from "../types/workspace";

const emptyWorkspace: WorkspaceSnapshot = {
  conversations: [],
  trashedConversations: [],
  recentFiles: [],
  sourceFiles: [],
  activeConversationId: null,
  messages: [],
  analysis: null,
  notes: "",
  reminders: [],
};

function getErrorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) {
    return "요청을 처리하지 못했어요. 잠시 후 다시 시도해 주세요.";
  }
  if (error.code === "ECONNABORTED" || error.code === "ETIMEDOUT") {
    return "처리 시간이 초과됐어요. 다시 시도해 주세요.";
  }
  if (!error.response) {
    return "서비스에 연결할 수 없어요. 인터넷 연결을 확인한 뒤 다시 시도해 주세요.";
  }

  const detail = error.response.data?.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (error.response.status === 422) {
    return "입력 내용을 확인해 주세요.";
  }
  if (error.response.status === 429) {
    return "현재 요청이 많아요. 잠시 후 다시 시도해 주세요.";
  }
  if (error.response.status === 504) {
    return "처리 시간이 초과됐어요. 다시 시도해 주세요.";
  }
  return "요청을 처리하지 못했어요. 잠시 후 다시 시도해 주세요.";
}

export function useTaskWorkspace() {
  const [workspace, setWorkspace] = useState<WorkspaceSnapshot>(emptyWorkspace);
  const [message, setMessage] = useState("");
  const [attachments, setAttachments] = useState<PendingFile[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [dueReminders, setDueReminders] = useState<ReminderSummary[]>([]);
  const notifiedReminderIds = useRef(new Set<string>());

  const loadWorkspace = useCallback(async (conversationId?: string) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      setWorkspace(await getWorkspace(conversationId));
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
      setWorkspace((current) => ({ ...emptyWorkspace, notes: current.notes }));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timerId = window.setTimeout(() => void loadWorkspace(), 0);
    return () => window.clearTimeout(timerId);
  }, [loadWorkspace]);

  const activeConversation = useMemo(
    () =>
      workspace.conversations.find(
        (item) => item.id === workspace.activeConversationId,
      ) ?? null,
    [workspace.activeConversationId, workspace.conversations],
  );

  const selectConversation = useCallback(
    async (conversationId: string) => {
      await loadWorkspace(conversationId);
    },
    [loadWorkspace],
  );

  const startConversation = useCallback(() => {
    setWorkspace((current) => ({
      ...current,
      activeConversationId: null,
      messages: [],
      sourceFiles: [],
      analysis: null,
      notes: "",
      reminders: [],
    }));
    setMessage("");
    setAttachments([]);
    setErrorMessage(null);
  }, []);

  const submitMessage = useCallback(async () => {
    const trimmedMessage = message.trim();
    if (!trimmedMessage && attachments.length === 0) {
      setErrorMessage("업무 지시 또는 파일을 입력해 주세요.");
      return;
    }
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      const response = await sendChat({
        conversation_id: workspace.activeConversationId,
        message: trimmedMessage,
        files: attachments.map((file) => ({
          name: file.name,
          mime_type: file.mimeType,
          content_base64: file.contentBase64,
        })),
      });
      const refreshed = await getWorkspace(response.conversation_id);
      setWorkspace({
        ...refreshed,
        analysis: response.analysis ?? refreshed.analysis,
      });
      setMessage("");
      setAttachments([]);
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }, [attachments, message, workspace.activeConversationId]);

  const transcribeRecording = useCallback(
    async (audioBlob: Blob) => {
      setIsTranscribing(true);
      setErrorMessage(null);
      try {
        const arrayBuffer = await audioBlob.arrayBuffer();
        const bytes = new Uint8Array(arrayBuffer);
        let binary = "";
        const chunkSize = 32_768;
        for (let index = 0; index < bytes.length; index += chunkSize) {
          binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
        }
        const transcript = await transcribeAudio({
          name: `tasklens-recording-${Date.now()}.webm`,
          mime_type: audioBlob.type || "audio/webm",
          content_base64: btoa(binary),
        });
        setMessage((current) => [current.trim(), transcript].filter(Boolean).join("\n"));
      } catch (error) {
        setErrorMessage(getErrorMessage(error));
      } finally {
        setIsTranscribing(false);
      }
    },
    [],
  );

  const changeTask = useCallback(
    async (taskId: string, changes: TaskUpdatePayload): Promise<boolean> => {
      const conversationId = workspace.activeConversationId;
      if (!conversationId) return false;
      setErrorMessage(null);
      try {
        const analysis = await updateTask(conversationId, taskId, changes);
        setWorkspace((current) => ({ ...current, analysis }));
        return true;
      } catch (error) {
        setErrorMessage(getErrorMessage(error));
        return false;
      }
    },
    [workspace.activeConversationId],
  );

  const removeTask = useCallback(
    async (taskId: string) => {
      const conversationId = workspace.activeConversationId;
      if (!conversationId) return;
      setErrorMessage(null);
      try {
        const analysis = await deleteTask(conversationId, taskId);
        setWorkspace((current) => ({ ...current, analysis }));
      } catch (error) {
        setErrorMessage(getErrorMessage(error));
      }
    },
    [workspace.activeConversationId],
  );

  const changeConversationTitle = useCallback(
    async (conversationId: string, title: string) => {
      setErrorMessage(null);
      try {
        await renameConversation(conversationId, title);
        await loadWorkspace(conversationId);
      } catch (error) {
        setErrorMessage(getErrorMessage(error));
      }
    },
    [loadWorkspace],
  );

  const moveConversationToTrash = useCallback(
    async (conversationId: string) => {
      setErrorMessage(null);
      try {
        await trashConversation(conversationId);
        await loadWorkspace();
      } catch (error) {
        setErrorMessage(getErrorMessage(error));
      }
    },
    [loadWorkspace],
  );

  const restoreTrashedConversation = useCallback(
    async (conversationId: string) => {
      setErrorMessage(null);
      try {
        await restoreConversation(conversationId);
        await loadWorkspace(conversationId);
      } catch (error) {
        setErrorMessage(getErrorMessage(error));
      }
    },
    [loadWorkspace],
  );

  const removeConversationPermanently = useCallback(
    async (conversationId: string) => {
      setErrorMessage(null);
      try {
        await deleteConversationPermanently(conversationId);
        await loadWorkspace();
      } catch (error) {
        setErrorMessage(getErrorMessage(error));
      }
    },
    [loadWorkspace],
  );

  const changeNotes = useCallback((content: string) => {
    setWorkspace((current) => ({ ...current, notes: content }));
  }, []);

  const persistNotes = useCallback(async (): Promise<boolean> => {
    const conversationId = workspace.activeConversationId;
    if (!conversationId) return false;
    setErrorMessage(null);
    try {
      await saveNotes(conversationId, workspace.notes);
      return true;
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
      return false;
    }
  }, [workspace.activeConversationId, workspace.notes]);

  const addReminder = useCallback(
    async (
      taskId: string | undefined,
      reminderMessage: string,
      remindAt: string,
    ): Promise<boolean> => {
      const conversationId = workspace.activeConversationId;
      if (!conversationId) return false;
      setErrorMessage(null);
      try {
        const reminder = await createReminder({
          conversationId,
          taskId,
          message: reminderMessage,
          remindAt,
        });
        setWorkspace((current) => ({
          ...current,
          reminders: [...current.reminders, reminder].sort((left, right) =>
            left.remindAt.localeCompare(right.remindAt),
          ),
        }));
        return true;
      } catch (error) {
        setErrorMessage(getErrorMessage(error));
        return false;
      }
    },
    [workspace.activeConversationId],
  );

  const dismissReminder = useCallback(async (reminderId: string) => {
    try {
      await updateReminderStatus(reminderId, "dismissed");
      setDueReminders((current) => current.filter((item) => item.id !== reminderId));
      setWorkspace((current) => ({
        ...current,
        reminders: current.reminders.map((item) =>
          item.id === reminderId ? { ...item, status: "dismissed" } : item,
        ),
      }));
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    }
  }, []);

  const checkReminders = useCallback(async () => {
    try {
      const due = await getDueReminders();
      setDueReminders(due);
      if (typeof Notification === "undefined" || Notification.permission !== "granted") {
        return;
      }
      for (const reminder of due) {
        if (notifiedReminderIds.current.has(reminder.id)) continue;
        notifiedReminderIds.current.add(reminder.id);
        new Notification("TaskLens 업무 알림", { body: reminder.message });
        await updateReminderStatus(reminder.id, "delivered");
      }
      setDueReminders([]);
    } catch {
      // 알림 폴링 실패는 사용자의 주 작업을 막지 않아요.
    }
  }, []);

  useEffect(() => {
    const initialTimerId = window.setTimeout(() => void checkReminders(), 0);
    const intervalId = window.setInterval(() => void checkReminders(), 60_000);
    return () => {
      window.clearTimeout(initialTimerId);
      window.clearInterval(intervalId);
    };
  }, [checkReminders]);

  return {
    workspace,
    activeConversation,
    message,
    attachments,
    isLoading,
    isSubmitting,
    isTranscribing,
    errorMessage,
    dueReminders,
    setMessage,
    setAttachments,
    selectConversation,
    startConversation,
    submitMessage,
    transcribeRecording,
    changeTask,
    removeTask,
    changeConversationTitle,
    moveConversationToTrash,
    restoreTrashedConversation,
    removeConversationPermanently,
    changeNotes,
    persistNotes,
    addReminder,
    dismissReminder,
    checkReminders,
  };
}