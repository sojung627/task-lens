import { AnalysisPanel } from "../components/AnalysisPanel";
import { AppHeader } from "../components/AppHeader";
import { ChatPanel } from "../components/ChatPanel";
import { ReminderToast } from "../components/ReminderToast";
import { Sidebar } from "../components/Sidebar";
import { useTaskWorkspace } from "../hooks/useTaskWorkspace";

// TaskLens의 전체 작업 화면과 자동 토스트 알림을 구성한다.
export default function Home() {
  const {
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
  } = useTaskWorkspace();

  return (
    <div
      className="min-h-screen bg-[#fbfbfe] bg-[radial-gradient(circle_at_48%_7%,rgba(125,84,255,0.07),transparent_24rem)] text-[#17142f]"
      aria-busy={isLoading}
    >
      <AppHeader
        dueReminderCount={dueReminders.length}
        onCheckReminders={() => void checkReminders()}
      />
      <ReminderToast
        reminders={dueReminders}
        onDismiss={(reminderId) => void dismissReminder(reminderId)}
      />

      <div className="hidden border-b border-[#e9e7f3] bg-white p-3 max-[720px]:flex max-[720px]:items-center max-[720px]:gap-2">
        <button
          className="shrink-0 rounded-lg border-0 bg-[#7546e5] px-3 py-2 text-xs font-bold text-white"
          type="button"
          onClick={startConversation}
        >
          <i className="fa-solid fa-plus mr-1.5" />새 대화
        </button>
        <select
          className="min-w-0 flex-1 rounded-lg border border-[#e1ddeb] bg-white px-3 py-2 text-xs"
          value={workspace.activeConversationId ?? ""}
          onChange={(event) => {
            if (event.target.value) void selectConversation(event.target.value);
          }}
        >
          <option value="">새로운 업무 정리</option>
          {workspace.conversations.map((conversation) => (
            <option value={conversation.id} key={conversation.id}>
              {conversation.title}
            </option>
          ))}
        </select>
      </div>

      <div className="grid min-h-[calc(100vh-72px)] grid-cols-[250px_minmax(480px,1fr)_minmax(350px,410px)] max-[1180px]:grid-cols-[220px_minmax(450px,1fr)_340px] max-[960px]:grid-cols-[210px_minmax(0,1fr)] max-[720px]:block">
        <Sidebar
          conversations={workspace.conversations}
          trashedConversations={workspace.trashedConversations}
          recentFiles={workspace.recentFiles}
          activeConversationId={workspace.activeConversationId}
          onCreateConversation={startConversation}
          onSelectConversation={(conversationId) => void selectConversation(conversationId)}
          onRenameConversation={(conversationId, title) =>
            void changeConversationTitle(conversationId, title)
          }
          onTrashConversation={(conversationId) =>
            void moveConversationToTrash(conversationId)
          }
          onRestoreConversation={(conversationId) =>
            void restoreTrashedConversation(conversationId)
          }
          onDeletePermanently={(conversationId) =>
            void removeConversationPermanently(conversationId)
          }
        />
        <ChatPanel
          activeConversation={activeConversation}
          messages={workspace.messages}
          message={message}
          attachments={attachments}
          isSubmitting={isSubmitting}
          isTranscribing={isTranscribing}
          errorMessage={errorMessage}
          onMessageChange={setMessage}
          onAttachmentsChange={setAttachments}
          onSubmit={() => void submitMessage()}
          onTranscribeRecording={(blob) => void transcribeRecording(blob)}
        />
        <AnalysisPanel
          activeConversationId={workspace.activeConversationId}
          analysis={workspace.analysis}
          sourceFiles={workspace.sourceFiles}
          notes={workspace.notes}
          reminders={workspace.reminders}
          dueReminders={dueReminders}
          onChangeTask={changeTask}
          onRemoveTask={(taskId) => void removeTask(taskId)}
          onNotesChange={changeNotes}
          onSaveNotes={persistNotes}
          onAddReminder={addReminder}
          onDismissReminder={(reminderId) => void dismissReminder(reminderId)}
        />
      </div>
    </div>
  );
}