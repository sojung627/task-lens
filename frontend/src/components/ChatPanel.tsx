import type { Dispatch, SetStateAction } from "react";
import type { ChatAttachment, ChatMessage, ConversationSummary } from "../types/workspace";

interface ChatPanelProps {
  activeConversation: ConversationSummary | null;
  messages: ChatMessage[];
  message: string;
  attachments: ChatAttachment[];
  isSubmitting: boolean;
  errorMessage: string | null;
  onMessageChange: (value: string) => void;
  onAttachmentsChange: Dispatch<SetStateAction<ChatAttachment[]>>;
  onSubmit: () => void;
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <article className={`flex items-start gap-3 ${isUser ? "justify-end" : ""}`}>
      {!isUser && <div className="grid h-[42px] w-[42px] shrink-0 place-items-center rounded-full bg-[#f5f1ff] text-center text-[8px] text-[#908aa0]">이미지 필요</div>}
      <div className={`max-w-[min(620px,82%)] rounded-xl px-[18px] pb-[13px] pt-[17px] ${isUser ? "border-0 bg-gradient-to-br from-[#ede5ff] to-[#f5f1ff]" : "border border-[#e1deeb] bg-white"}`}>
        <p className="m-0 whitespace-pre-wrap leading-[1.7]">{message.content}</p>
        {message.attachments.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {message.attachments.map((attachment) => (
              <span className="inline-flex items-center gap-2 rounded-lg bg-white/80 px-[10px] py-[7px] text-[11px] text-[#5d566f]" key={attachment.id}>
                <i className="fa-regular fa-file" />{attachment.name}<small className="font-bold text-[#7b4bea]">{attachment.extension.toUpperCase()}</small>
              </span>
            ))}
          </div>
        )}
        <time className="mt-[9px] block text-right text-[10px] text-[#9892aa]">{message.createdAt}</time>
      </div>
    </article>
  );
}

export function ChatPanel({ activeConversation, messages, message, attachments, isSubmitting, errorMessage, onMessageChange, onAttachmentsChange, onSubmit }: ChatPanelProps) {
  const canSubmit = message.trim().length > 0 || attachments.length > 0;
  void onAttachmentsChange;

  return (
    <main className="flex min-h-[calc(100vh-72px)] min-w-0 flex-col bg-white/70 px-8 pb-3.5 max-[1180px]:px-5 max-[720px]:px-3.5">
      <header className="flex h-[78px] shrink-0 items-center gap-2">
        <h1 className="m-0 text-lg font-bold tracking-[-0.02em]">{activeConversation?.title ?? "새로운 대화"}</h1>
        <button type="button" className="border-0 bg-transparent" aria-label="대화 메뉴 열기"><i className="fa-solid fa-chevron-down" /></button>
      </header>

      <section className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto grid max-w-[760px] gap-[26px] py-3 pb-7">
          {messages.map((chatMessage) => <MessageBubble key={chatMessage.id} message={chatMessage} />)}
        </div>
      </section>

      <section className="mx-auto mt-auto w-full max-w-[760px] rounded-[13px] border border-[#dedbe8] bg-white px-[15px] py-[13px] shadow-[0_12px_35px_rgba(53,41,91,0.07)]" aria-label="메시지 작성">
        <textarea className="min-h-[76px] w-full resize-none border-0 bg-transparent text-[#252039] outline-none" value={message} onChange={(event) => onMessageChange(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); if (canSubmit && !isSubmitting) onSubmit(); } }} placeholder="메시지를 입력하거나 파일을 업로드하세요..." rows={3} />
        <div className="flex items-center justify-between gap-3">
          <div className="flex flex-wrap gap-[7px]">
            {[
              ["fa-solid fa-arrow-up-from-bracket", "파일 업로드"],
              ["fa-regular fa-paste", "텍스트 붙여넣기"],
              ["fa-solid fa-microphone", "음성 업로드"],
              ["fa-regular fa-image", "이미지 캡처"],
            ].map(([icon, label]) => (
              <button key={label} type="button" className="rounded-lg border border-[#e3e0eb] bg-white px-[11px] py-[9px] text-[11px] max-[1180px]:text-0"><i className={`${icon} mr-1.5 max-[1180px]:mr-0 max-[1180px]:text-[13px]`} />{label}</button>
            ))}
          </div>
          <button className="h-11 w-11 shrink-0 rounded-[10px] border-0 bg-gradient-to-br from-[#9c64ff] to-[#6b38eb] text-white shadow-[0_8px_18px_rgba(108,57,235,0.24)] disabled:cursor-not-allowed disabled:opacity-45" type="button" disabled={!canSubmit || isSubmitting} onClick={onSubmit} aria-label="분석 요청 보내기">
            <i className={isSubmitting ? "fa-solid fa-spinner fa-spin" : "fa-solid fa-paper-plane"} />
          </button>
        </div>
      </section>
      {errorMessage && <p className="mx-auto mt-2.5 text-center text-[11px] text-[#7b4bea]">{errorMessage}</p>}
      <p className="mx-auto mt-2.5 text-center text-[11px] text-[#9a96aa]">AI는 실수를 할 수 있으니 중요한 정보는 다시 확인해 주세요.</p>
    </main>
  );
}
