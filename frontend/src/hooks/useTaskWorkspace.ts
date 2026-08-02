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

const GENERIC_ERROR_MESSAGE = "죄송합니다. 잠시 후 다시 시도해 주세요.";

// 요청 오류를 사용자에게 보여 줄 안전한 공통 문구로 변환한다.
function getErrorMessage(error: unknown): string {
  // 서버 내부 사유나 개발자용 문구는 사용자 화면에 노출하지 않는다.
  if (axios.isAxiosError(error)) {
    console.error("TaskLens request failed", {
      code: error.code,
      status: error.response?.status,
    });
  } else {
    console.error("TaskLens request failed", error);
  }
  return GENERIC_ERROR_MESSAGE;
}

// TaskLens 작업공간의 조회, 채팅, 체크리스트, 알림 상태를 관리한다.
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
      // POST /chat 성공 결과를 먼저 화면에 반영해 후속 조회 실패가 전송 실패로 보이지 않게 한다.
      setWorkspace((current) => ({
        ...current,
        activeConversationId: response.conversation_id,
        messages: [
          ...current.messages.filter((item) => item.id !== response.message.id),
          response.message,
        ],
        analysis: response.analysis ?? current.analysis,
      }));
      setMessage("");
      setAttachments([]);

      try {
        const refreshed = await getWorkspace(response.conversation_id);
        setWorkspace({
          ...refreshed,
          analysis: response.analysis ?? refreshed.analysis,
        });
      } catch (refreshError) {
        // 채팅과 파일 생성은 이미 성공했으므로 새로고침 실패만 개발자 콘솔에 남긴다.
        console.warn("TaskLens workspace refresh failed after successful chat", refreshError);
      }
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

  // 예약 시간이 지난 알림을 조회해 페이지 내부 토스트로 표시하고 전송 상태를 저장한다.
  const checkReminders = useCallback(async () => {
    try {
      const due = await getDueReminders();
      const newDueReminders = due.filter(
        (reminder) => !notifiedReminderIds.current.has(reminder.id),
      );

      if (newDueReminders.length === 0) return;

      const deliveredReminders: ReminderSummary[] = [];

      for (const reminder of newDueReminders) {
        notifiedReminderIds.current.add(reminder.id);
        try {
          await updateReminderStatus(reminder.id, "delivered");
          deliveredReminders.push(reminder);
        } catch {
          notifiedReminderIds.current.delete(reminder.id);
        }
      }

      if (deliveredReminders.length === 0) return;

      setDueReminders((current) => {
        const currentIds = new Set(current.map((reminder) => reminder.id));
        return [
          ...current,
          ...deliveredReminders.filter((reminder) => !currentIds.has(reminder.id)),
        ];
      });

      const deliveredIdSet = new Set(
        deliveredReminders.map((reminder) => reminder.id),
      );
      setWorkspace((current) => ({
        ...current,
        reminders: current.reminders.map((reminder) =>
          deliveredIdSet.has(reminder.id)
            ? { ...reminder, status: "delivered" }
            : reminder,
        ),
      }));
    } catch {
      // 알림 확인 실패는 채팅과 체크리스트 기능을 막지 않는다.
    }
  }, []);

  useEffect(() => {
    const initialTimerId = window.setTimeout(() => void checkReminders(), 0);
    const intervalId = window.setInterval(() => void checkReminders(), 10_000);
    return () => {
      window.clearTimeout(initialTimerId);
      window.clearInterval(intervalId);
    };
  }, [checkReminders]);

  useEffect(() => {
    const pendingTimes = workspace.reminders
      .filter((reminder) => reminder.status === "pending")
      .map((reminder) => Date.parse(reminder.remindAt))
      .filter(Number.isFinite);

    if (pendingTimes.length === 0) return undefined;

    const nextReminderTime = Math.min(...pendingTimes);
    let timerId: number;

    // 브라우저 최대 타이머 길이를 넘는 먼 미래 알림도 단계적으로 예약한다.
    const scheduleReminderCheck = () => {
      const remainingMilliseconds = nextReminderTime - Date.now();

      if (remainingMilliseconds <= 0) {
        void checkReminders();
        return;
      }

      timerId = window.setTimeout(
        scheduleReminderCheck,
        Math.min(remainingMilliseconds, 2_147_000_000),
      );
    };

    scheduleReminderCheck();

    return () => window.clearTimeout(timerId);
  }, [checkReminders, workspace.reminders]);

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