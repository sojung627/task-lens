import { createPortal } from "react-dom";

import type { ReminderSummary } from "../types/workspace";

interface ReminderToastProps {
  reminders: ReminderSummary[];
  onDismiss: (reminderId: string) => void;
}

// 예약 시각을 사용자가 읽기 쉬운 한국어 시각으로 변환한다.
function formatReminderTime(remindAt: string): string {
  return new Date(remindAt).toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

// 다른 스타일보다 우선하도록 토스트를 화면 오른쪽 아래에 강제 고정한다.
function pinToastToBottomRight(element: HTMLElement | null): void {
  if (!element) return;

  element.style.setProperty("position", "fixed", "important");
  element.style.setProperty("top", "auto", "important");
  element.style.setProperty("right", "24px", "important");
  element.style.setProperty("bottom", "24px", "important");
  element.style.setProperty("left", "auto", "important");
  element.style.setProperty("margin", "0", "important");
  element.style.setProperty("transform", "none", "important");
}

// 예약 시간이 된 업무를 화면 녹화에 포함되는 페이지 내부 토스트로 표시한다.
export function ReminderToast({ reminders, onDismiss }: ReminderToastProps) {
  if (typeof document === "undefined" || reminders.length === 0) return null;

  return createPortal(
    <section
      ref={pinToastToBottomRight}
      className="z-[9999] grid max-h-[calc(100vh-48px)] w-[min(380px,calc(100vw-32px))] gap-3 overflow-y-auto"
      style={{
        position: "fixed",
        top: "auto",
        right: "24px",
        bottom: "24px",
        left: "auto",
        margin: 0,
        transform: "none",
      }}
      aria-label="업무 알림"
      aria-live="assertive"
    >
      {reminders.map((reminder) => (
        <article
          className="overflow-hidden rounded-2xl border border-[#ded3fa] bg-white"
          role="alert"
          key={reminder.id}
        >
          <div className="h-1 bg-gradient-to-r from-[#9b6cff] via-[#7b49e8] to-[#5b35d5]" />
          <div className="flex items-start gap-3 p-4">
            <span
              className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#f1ebff] text-[#7445e8]"
              aria-hidden="true"
            >
              <i className="fa-solid fa-bell" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-3">
                <strong className="text-sm text-[#211a38]">TaskLens 업무 알림</strong>
                <time className="shrink-0 text-[11px] text-[#82798f]">
                  {formatReminderTime(reminder.remindAt)}
                </time>
              </div>
              <p className="mt-1.5 break-words text-[13px] leading-5 text-[#514960]">
                {reminder.message}
              </p>
              <div className="mt-3 flex justify-end">
                <button
                  className="rounded-lg border-0 bg-[#7546e5] px-3 py-1.5 text-xs font-bold text-white transition hover:bg-[#6538d5] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#7546e5]"
                  type="button"
                  onClick={() => onDismiss(reminder.id)}
                >
                  확인
                </button>
              </div>
            </div>
          </div>
        </article>
      ))}
    </section>,
    document.body,
  );
}