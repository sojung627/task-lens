import { AnalysisPanel } from "../components/AnalysisPanel";
import { AppHeader } from "../components/AppHeader";
import { ChatPanel } from "../components/ChatPanel";
import { Sidebar } from "../components/Sidebar";
import { useTaskWorkspace } from "../hooks/useTaskWorkspace";

export default function Home() {
  const {
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
  } = useTaskWorkspace();

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_48%_7%,rgba(125,84,255,0.07),transparent_24rem)] bg-[#fbfbfe] text-[#17142f]"
        aria-busy={isLoading}
    >
      <AppHeader />
      <div className="grid min-h-[calc(100vh-72px)] grid-cols-[250px_minmax(480px,1fr)_minmax(350px,410px)] max-[1180px]:grid-cols-[220px_minmax(450px,1fr)_340px] max-[960px]:grid-cols-[210px_minmax(0,1fr)] max-[720px]:block">
        <Sidebar
          conversations={workspace.conversations}
          recentFiles={workspace.recentFiles}
          activeConversationId={workspace.activeConversationId}
          onCreateConversation={startConversation}
          onSelectConversation={selectConversation}
        />
        <ChatPanel
          activeConversation={activeConversation}
          messages={workspace.messages}
          message={message}
          attachments={attachments}
          isSubmitting={isSubmitting}
          errorMessage={errorMessage}
          onMessageChange={setMessage}
          onAttachmentsChange={setAttachments}
          onSubmit={submitMessage}
        />
        <AnalysisPanel
          analysis={workspace.analysis}
          sourceFiles={workspace.recentFiles}
          onToggleChecklist={toggleChecklist}
        />
      </div>
    </div>
  );
}
