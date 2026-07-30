export function AppHeader() {
  return (
    <header
        className="sticky top-0 z-30 flex h-[72px] items-center justify-between border-b border-[#e9e7f3] bg-white/95 px-[26px] backdrop-blur-2xl max-[720px]:px-3.5"
    >
      <a
        className="inline-flex items-center gap-3 text-[25px] font-extrabold tracking-[-0.03em] text-[#17142f] no-underline"
        href="/" aria-label="TaskLens 홈"
      >
        <span
            className="grid h-[34px] w-[34px] place-items-center rounded-[9px] bg-gradient-to-br from-[#9c6cff] to-[#7040ef] text-white shadow-[0_8px_20px_rgba(113,65,238,0.25)]"
            aria-hidden="true"
        >
          <i className="fa-solid fa-magnifying-glass" />
        </span>
        <span>TaskLens</span>
      </a>
      <nav className="flex items-center gap-3" aria-label="사용자 메뉴">
        <button
            className="inline-flex items-center gap-2 rounded-xl border-0 bg-[#f4efff] px-[13px] py-[9px] font-bold text-[#7445e8] max-[720px]:[&>span]:hidden"
            type="button"
        >
          <i className="fa-solid fa-crown" aria-hidden="true" />
          <span>프리미엄</span>
        </button>
        <button
            className="h-[38px] w-[38px] rounded-full border-0 bg-transparent"
            type="button"
            aria-label="알림"
        >
            <i className="fa-regular fa-bell" />
        </button>
        <button
            className="h-[38px] w-[38px] rounded-full border-0 bg-[#efe8ff] text-[#7b4ae9]"
            type="button" aria-label="프로필"
        >
            <i className="fa-solid fa-user" />
        </button>
      </nav>
    </header>
  );
}
