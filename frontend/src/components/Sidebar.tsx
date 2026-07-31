import type { ConversationSummary, SourceFile } from "../types/workspace";

interface SidebarProps {
  conversations: ConversationSummary[];
  recentFiles: SourceFile[];
  activeConversationId: string | null;
  onCreateConversation: () => void;
  onSelectConversation: (conversationId: string) => void;
}

function FileIcon({ extension }: { extension: string }) {
  const normalizedExtension = extension.toLowerCase();
  const iconClass = normalizedExtension.match(/png|jpg|jpeg|gif|webp/)
    ? "fa-regular fa-image"
    : normalizedExtension.match(/mp3|wav|m4a/)
      ? "fa-solid fa-volume-high"
      : "fa-regular fa-file-lines";

  return <i className={iconClass} aria-hidden="true" />;
}

export function Sidebar({ conversations, recentFiles, activeConversationId, onCreateConversation, onSelectConversation }: SidebarProps) {
  return (
    <aside
        className="flex min-h-[calc(100vh-72px)] flex-col gap-[18px] border-r border-[#e9e7f3] bg-white/90 px-4 pb-[18px] pt-5 max-[720px]:hidden"
    >
      <button
        className="h-11 rounded-[9px] border-0 bg-gradient-to-br from-[#8c54ff] to-[#6b37ec] font-bold text-white shadow-[0_10px_22px_rgba(107,55,236,0.24)]"
        type="button"
        onClick={onCreateConversation}
      >
        <i className="fa-solid fa-plus mr-[9px]" />새 대화
      </button>

      <label
        className="grid h-[42px] grid-cols-[22px_1fr_20px] items-center gap-[7px] rounded-[9px] border border-[#e3e0ed] bg-white px-3 text-[#8d89a2]"
      >
        <i className="fa-solid fa-magnifying-glass" />
        <input
            className="min-w-0 border-0 bg-transparent text-[#27223e] outline-none"
            type="search"
            placeholder="대화 검색"
        />
        <i className="fa-solid fa-filter" />
      </label>

      <section className="min-w-0">
        <div
            className="flex items-center justify-between px-2 pb-2.5 pt-1"
        >
          <h2 className="m-0 text-[13px] font-bold">
            최근 대화
          </h2>
          <i className="fa-solid fa-chevron-up text-[11px] text-[#777289]" />
        </div>
        {conversations.length > 0 ? (
          <ul className="m-0 grid list-none gap-[3px] p-0">
            {conversations.map((conversation) => {
              const isActive = conversation.id === activeConversationId;
              return (
                <li key={conversation.id}>
                  <button
                    className={`grid min-h-[58px] w-full grid-cols-[22px_minmax(0,1fr)_12px] items-center gap-2 rounded-[9px] border-0 px-[9px] py-2.5 text-left hover:bg-gradient-to-r hover:from-[#f1ebff] hover:to-[#f8f5ff]
                    ${isActive ? "bg-gradient-to-r from-[#f1ebff] to-[#f8f5ff]" : "bg-transparent"}`}
                    type="button"
                    onClick={() => onSelectConversation(conversation.id)}
                  >
                    <i
                        className={`fa-regular fa-message
                        ${isActive ? "text-[#7950e8]" : ""}`}
                    />
                    <span className="grid min-w-0 gap-1">
                      <strong
                        className="overflow-hidden text-ellipsis whitespace-nowrap text-[13px]"
                      >
                            {conversation.title}
                      </strong>
                      <small
                        className="text-[11px] text-[#9893aa]"
                      >
                        {conversation.preview ?? conversation.updatedAt}
                      </small>
                    </span>
                    <i className="fa-solid fa-chevron-right" />
                  </button>
                </li>
              );
            })}
          </ul>
        ) : <p className="mx-2 my-1 text-xs text-[#9994a8]">저장된 대화가 없어요.</p>}
      </section>

      <section className="mt-1.5 min-w-0">
        <div className="flex items-center justify-between px-2 pb-2.5 pt-1">
          <h2 className="m-0 text-[13px] font-bold">
            최근 분석
          </h2>
          <i className="fa-solid fa-chevron-up text-[11px] text-[#777289]" />
        </div>
        {recentFiles.length > 0 ? (
          <ul className="m-0 grid list-none gap-2.5 px-2 py-0">
            {recentFiles.map((file) => (
              <li
                className="grid min-w-0 grid-cols-[34px_minmax(0,1fr)] items-center gap-[9px]"
                key={file.id}
              >
                <span
                    className="grid h-[34px] w-[34px] place-items-center rounded-[9px] bg-[#f0eaff] text-[#7143e8]"
                >
                    <FileIcon extension={file.extension} />
                </span>
                <span className="grid min-w-0 gap-[3px]">
                  <strong className="overflow-hidden text-ellipsis whitespace-nowrap text-[13px]">
                    {file.name}
                  </strong>
                  <small className="text-[11px] text-[#9893aa]">
                    {file.extension.toUpperCase()} · {file.uploadedAt}
                  </small>
                </span>
              </li>
            ))}
          </ul>
        ) : <p className="mx-2 my-1 text-xs text-[#9994a8]">분석한 파일이 없어요.</p>}
      </section>

      <div className="mt-auto grid gap-3.5">
        <button
            className="h-[45px] w-full rounded-[9px] border border-[#e4e1ed] bg-white px-[15px] text-left"
            type="button"
        >
            <i className="fa-regular fa-trash-can mr-2.5" />
            휴지통
        </button>
        <button
            className="grid min-h-[68px] w-full grid-cols-[38px_minmax(0,1fr)_16px] items-center gap-2.5 rounded-[9px] border border-[#e4e1ed] bg-white p-2.5 text-left"
            type="button"
        >
          <span
            className="grid h-[38px] w-[38px] place-items-center rounded-full bg-gradient-to-br from-[#a478ff] to-[#7145e8] text-white"
          >
            <i className="fa-solid fa-user" />
          </span>
          <span className="grid gap-[3px]">
            <strong>
                계정
            </strong>
            <small className="text-[11px] text-[#9893aa]">
                프로필 보기
            </small>
          </span>
          <i className="fa-solid fa-ellipsis-vertical" />
        </button>
      </div>
    </aside>
  );
}
