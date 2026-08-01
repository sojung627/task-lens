import { useMemo, useState } from "react";

import { resolveDownloadUrl } from "../api/taskApi";
import type { ConversationSummary, SourceFile } from "../types/workspace";

interface SidebarProps {
  conversations: ConversationSummary[];
  trashedConversations: ConversationSummary[];
  recentFiles: SourceFile[];
  activeConversationId: string | null;
  onCreateConversation: () => void;
  onSelectConversation: (conversationId: string) => void;
  onRenameConversation: (conversationId: string, title: string) => void;
  onTrashConversation: (conversationId: string) => void;
  onRestoreConversation: (conversationId: string) => void;
  onDeletePermanently: (conversationId: string) => void;
}

function FileIcon({ extension }: { extension: string }) {
  const normalizedExtension = extension.toLowerCase();
  const iconClass = normalizedExtension.match(/mp3|wav|m4a|webm/)
    ? "fa-solid fa-volume-high"
    : normalizedExtension === "pdf"
      ? "fa-regular fa-file-pdf"
      : "fa-regular fa-file-lines";
  return <i className={iconClass} aria-hidden="true" />;
}

export function Sidebar({
  conversations,
  trashedConversations,
  recentFiles,
  activeConversationId,
  onCreateConversation,
  onSelectConversation,
  onRenameConversation,
  onTrashConversation,
  onRestoreConversation,
  onDeletePermanently,
}: SidebarProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [showTrash, setShowTrash] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");

  const filteredConversations = useMemo(() => {
    const normalized = searchQuery.trim().toLowerCase();
    if (!normalized) return conversations;
    return conversations.filter((conversation) =>
      `${conversation.title} ${conversation.preview ?? ""}`.toLowerCase().includes(normalized),
    );
  }, [conversations, searchQuery]);

  const startEditing = (conversation: ConversationSummary) => {
    setEditingId(conversation.id);
    setEditingTitle(conversation.title);
  };

  const submitTitle = (conversationId: string) => {
    const normalized = editingTitle.trim();
    if (normalized) onRenameConversation(conversationId, normalized);
    setEditingId(null);
  };

  return (
    <aside className="flex min-h-[calc(100vh-72px)] flex-col gap-[18px] border-r border-[#e9e7f3] bg-white/90 px-4 pb-[18px] pt-5 max-[720px]:hidden">
      <button
        className="h-11 rounded-[9px] border-0 bg-gradient-to-br from-[#8c54ff] to-[#6b37ec] font-bold text-white shadow-[0_10px_22px_rgba(107,55,236,0.24)]"
        type="button"
        onClick={onCreateConversation}
      >
        <i className="fa-solid fa-plus mr-[9px]" />새 대화
      </button>

      <label className="grid h-[42px] grid-cols-[22px_1fr] items-center gap-[7px] rounded-[9px] border border-[#e3e0ed] bg-white px-3 text-[#8d89a2]">
        <i className="fa-solid fa-magnifying-glass" />
        <input
          className="min-w-0 border-0 bg-transparent text-[#27223e] outline-none"
          type="search"
          placeholder="대화 검색"
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
        />
      </label>

      <section className="min-w-0">
        <div className="flex items-center justify-between px-2 pb-2.5 pt-1">
          <h2 className="m-0 text-[13px] font-bold">최근 대화</h2>
          <span className="text-[11px] text-[#8f899d]">{filteredConversations.length}개</span>
        </div>
        {filteredConversations.length > 0 ? (
          <ul className="m-0 grid max-h-[34vh] list-none gap-[3px] overflow-y-auto p-0">
            {filteredConversations.map((conversation) => {
              const isActive = conversation.id === activeConversationId;
              return (
                <li
                  className={`group rounded-[9px] ${
                    isActive ? "bg-gradient-to-r from-[#f1ebff] to-[#f8f5ff]" : ""
                  }`}
                  key={conversation.id}
                >
                  {editingId === conversation.id ? (
                    <div className="flex items-center gap-2 p-2">
                      <input
                        className="min-w-0 flex-1 rounded-lg border border-[#dcd6e9] px-2 py-1.5 text-xs outline-none focus:border-[#8b59ea]"
                        value={editingTitle}
                        autoFocus
                        onChange={(event) => setEditingTitle(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") submitTitle(conversation.id);
                          if (event.key === "Escape") setEditingId(null);
                        }}
                      />
                      <button
                        className="border-0 bg-transparent text-[#7244e4]"
                        type="button"
                        aria-label="이름 저장"
                        onClick={() => submitTitle(conversation.id)}
                      >
                        <i className="fa-solid fa-check" />
                      </button>
                    </div>
                  ) : (
                    <div className="grid grid-cols-[1fr_auto] items-center">
                      <button
                        className="grid min-h-[58px] min-w-0 grid-cols-[22px_minmax(0,1fr)] items-center gap-2 border-0 bg-transparent px-[9px] py-2.5 text-left"
                        type="button"
                        onClick={() => onSelectConversation(conversation.id)}
                      >
                        <i
                          className={`fa-regular fa-message ${isActive ? "text-[#7950e8]" : ""}`}
                        />
                        <span className="grid min-w-0 gap-1">
                          <strong className="overflow-hidden text-ellipsis whitespace-nowrap text-[13px]">
                            {conversation.title}
                          </strong>
                          <small className="overflow-hidden text-ellipsis whitespace-nowrap text-[11px] text-[#9893aa]">
                            {conversation.preview ?? conversation.updatedAt}
                          </small>
                        </span>
                      </button>
                      <details className="relative mr-1">
                        <summary className="grid h-8 w-7 cursor-pointer list-none place-items-center rounded-lg text-[#8f899d] hover:bg-white">
                          <i className="fa-solid fa-ellipsis-vertical" />
                        </summary>
                        <div className="absolute right-0 top-8 z-20 grid w-28 rounded-lg border border-[#e4e0ed] bg-white p-1 text-xs shadow-lg">
                          <button
                            className="rounded-md border-0 bg-transparent px-2 py-2 text-left hover:bg-[#f5f1ff]"
                            type="button"
                            onClick={() => startEditing(conversation)}
                          >
                            이름 변경
                          </button>
                          <button
                            className="rounded-md border-0 bg-transparent px-2 py-2 text-left text-[#a64660] hover:bg-[#fff0f3]"
                            type="button"
                            onClick={() => onTrashConversation(conversation.id)}
                          >
                            휴지통 이동
                          </button>
                        </div>
                      </details>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="mx-2 my-1 text-xs text-[#9994a8]">조건에 맞는 대화가 없어요.</p>
        )}
      </section>

      <section className="mt-1.5 min-w-0">
        <div className="flex items-center justify-between px-2 pb-2.5 pt-1">
          <h2 className="m-0 text-[13px] font-bold">최근 파일</h2>
          <span className="text-[11px] text-[#8f899d]">{recentFiles.length}개</span>
        </div>
        {recentFiles.length > 0 ? (
          <ul className="m-0 grid max-h-[24vh] list-none gap-2.5 overflow-y-auto px-2 py-0">
            {recentFiles.map((file) => (
              <li className="grid min-w-0 grid-cols-[34px_minmax(0,1fr)] items-center gap-[9px]" key={file.id}>
                <span className="grid h-[34px] w-[34px] place-items-center rounded-[9px] bg-[#f0eaff] text-[#7143e8]">
                  <FileIcon extension={file.extension} />
                </span>
                <a
                  className="grid min-w-0 gap-[3px] text-inherit no-underline"
                  href={resolveDownloadUrl(file.downloadUrl)}
                  download={file.name}
                >
                  <strong className="overflow-hidden text-ellipsis whitespace-nowrap text-[13px]">
                    {file.name}
                  </strong>
                  <small className="text-[11px] text-[#9893aa]">
                    {file.extension.toUpperCase()} · {file.uploadedAt}
                  </small>
                </a>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mx-2 my-1 text-xs text-[#9994a8]">저장된 파일이 없어요.</p>
        )}
      </section>

      <div className="mt-auto">
        <button
          className="flex h-[45px] w-full items-center justify-between rounded-[9px] border border-[#e4e1ed] bg-white px-[15px] text-left"
          type="button"
          onClick={() => setShowTrash((current) => !current)}
        >
          <span><i className="fa-regular fa-trash-can mr-2.5" />휴지통</span>
          <span className="text-xs text-[#8f899d]">{trashedConversations.length}</span>
        </button>
        {showTrash && (
          <div className="mt-2 max-h-48 overflow-y-auto rounded-[9px] border border-[#e4e1ed] bg-white p-2">
            {trashedConversations.length > 0 ? (
              trashedConversations.map((conversation) => (
                <div className="grid grid-cols-[1fr_auto] items-center gap-2 border-b border-[#f0edf5] py-2 last:border-0" key={conversation.id}>
                  <span className="min-w-0 overflow-hidden text-ellipsis whitespace-nowrap text-xs">
                    {conversation.title}
                  </span>
                  <span className="flex gap-1">
                    <button
                      className="rounded-md border-0 bg-[#f1ecff] px-2 py-1 text-[10px] text-[#7042df]"
                      type="button"
                      onClick={() => onRestoreConversation(conversation.id)}
                    >
                      복원
                    </button>
                    <button
                      className="rounded-md border-0 bg-[#fff0f3] px-2 py-1 text-[10px] text-[#a64660]"
                      type="button"
                      onClick={() => onDeletePermanently(conversation.id)}
                    >
                      삭제
                    </button>
                  </span>
                </div>
              ))
            ) : (
              <p className="m-1 text-xs text-[#9994a8]">휴지통이 비어 있어요.</p>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}