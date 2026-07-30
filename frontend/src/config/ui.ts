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
