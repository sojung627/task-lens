const configuredChatFileMaxBytes = Number(import.meta.env.VITE_CHAT_FILE_MAX_BYTES);

// 채팅 첨부 파일의 최대 크기를 환경변수에서 읽고 올바르지 않으면 10KB를 사용한다.
export const chatFileMaxBytes =
  Number.isFinite(configuredChatFileMaxBytes) && configuredChatFileMaxBytes > 0
    ? Math.floor(configuredChatFileMaxBytes)
    : 10 * 1024;

export const uploadFormats = [
  "PNG",
  "JPG",
  "PDF",
  "TXT",
  "HWP",
  "DOCX",
  "MD",
  "MP3",
  "WAV",
  "MP4",
] as const;

export const analysisTabs = [
  { id: "analysis", label: "분석 결과" },
  { id: "sources", label: "소스 파일" },
  { id: "notes", label: "노트" },
] as const;

export type AnalysisTabId = (typeof analysisTabs)[number]["id"];