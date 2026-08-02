interface AppHeaderProps {
  dueReminderCount: number;
  onCheckReminders: () => void;
}

// TaskLens 로고와 현재 업무 알림 개수를 헤더에 표시한다.
export function AppHeader({ dueReminderCount, onCheckReminders }: AppHeaderProps) {
  return (
    <header className="sticky top-0 z-30 flex h-[72px] items-center justify-between border-b border-[#e9e7f3] bg-white/95 px-[26px] backdrop-blur-2xl max-[720px]:px-3.5">
      <a
        className="inline-flex items-center gap-3 text-[25px] font-extrabold tracking-[-0.03em] text-[#17142f] no-underline"
        href="/"
        aria-label="TaskLens 홈"
      >
        <span
          className="grid h-[34px] w-[34px] place-items-center rounded-[9px] bg-gradient-to-br from-[#9c6cff] to-[#7040ef] text-white shadow-[0_8px_20px_rgba(113,65,238,0.25)]"
          aria-hidden="true"
        >
          <i className="fa-solid fa-magnifying-glass" />
        </span>
        <span>TaskLens</span>
      </a>
      <div className="flex items-center gap-3">
        <span className="rounded-full bg-[#f4efff] px-3 py-2 text-xs font-bold text-[#7445e8] max-[560px]:hidden">
          문서 업무 자동 정리
        </span>
        <button
          className="relative grid h-[40px] w-[40px] place-items-center rounded-full border border-[#e6e1f1] bg-white text-[#6f667d]"
          type="button"
          aria-label="업무 알림 확인"
          onClick={onCheckReminders}
        >
          <i className="fa-regular fa-bell" />
          {dueReminderCount > 0 && (
            <span className="absolute -right-1 -top-1 grid h-5 min-w-5 place-items-center rounded-full bg-[#7b4ae9] px-1 text-[10px] font-bold text-white">
              {dueReminderCount}
            </span>
          )}
        </button>
      </div>
    </header>
  );
}