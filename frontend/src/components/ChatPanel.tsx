import { useEffect, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import { resolveDownloadUrl } from "../api/taskApi";
import type { ChatMessage, ConversationSummary, PendingFile } from "../types/workspace";

interface ChatPanelProps {
  activeConversation: ConversationSummary | null;
  messages: ChatMessage[];
  message: string;
  attachments: PendingFile[];
  isSubmitting: boolean;
  isTranscribing: boolean;
  errorMessage: string | null;
  onMessageChange: (value: string) => void;
  onAttachmentsChange: Dispatch<SetStateAction<PendingFile[]>>;
  onSubmit: () => void;
  onTranscribeRecording: (blob: Blob) => void;
}

const supportedExtensions = new Set([
  "txt",
  "md",
  "csv",
  "json",
  "xml",
  "yaml",
  "yml",
  "py",
  "js",
  "jsx",
  "ts",
  "tsx",
  "html",
  "css",
  "sql",
  "java",
  "c",
  "cpp",
  "h",
  "log",
  "pdf",
  "docx",
  "mp3",
  "mp4",
  "mpeg",
  "mpga",
  "m4a",
  "ogg",
  "wav",
  "webm",
  "flac",
]);
const maxFileSize = 10 * 1024 * 1024;

function formatSize(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] ?? "");
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <article className={`flex items-start gap-3 ${isUser ? "justify-end" : ""}`}>
      {!isUser && (
        <div className="grid h-[42px] w-[42px] shrink-0 place-items-center rounded-full bg-[#f5f1ff] text-[#7950e8]">
          <i className="fa-solid fa-wand-magic-sparkles" />
        </div>
      )}
      <div
        className={`max-w-[min(620px,84%)] rounded-2xl px-[18px] pb-[13px] pt-[17px] ${
          isUser
            ? "bg-gradient-to-br from-[#ede5ff] to-[#f5f1ff]"
            : "border border-[#e1deeb] bg-white"
        }`}
      >
        <p className="m-0 whitespace-pre-wrap leading-[1.7]">
          {message.content || "파일을 전송했어요."}
        </p>
        {message.attachments.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {message.attachments.map((attachment) => (
              <a
                className="inline-flex items-center gap-2 rounded-lg bg-white/80 px-[10px] py-[7px] text-[11px] text-[#5d566f] no-underline"
                href={resolveDownloadUrl(attachment.downloadUrl)}
                download={attachment.name}
                key={attachment.id}
              >
                <i className="fa-regular fa-file" />
                <span className="max-w-52 overflow-hidden text-ellipsis whitespace-nowrap">
                  {attachment.name}
                </span>
                <small className="font-bold text-[#7b4bea]">
                  {attachment.extension.toUpperCase()}
                </small>
                <i className="fa-solid fa-download" />
              </a>
            ))}
          </div>
        )}
        <time className="mt-[9px] block text-right text-[10px] text-[#9892aa]">
          {message.createdAt}
        </time>
      </div>
    </article>
  );
}

export function ChatPanel({
  activeConversation,
  messages,
  message,
  attachments,
  isSubmitting,
  isTranscribing,
  errorMessage,
  onMessageChange,
  onAttachmentsChange,
  onSubmit,
  onTranscribeRecording,
}: ChatPanelProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const scrollAnchorRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const speechRecognitionRef = useRef<SpeechRecognition | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const canSubmit = message.trim().length > 0 || attachments.length > 0;

  useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSubmitting]);

  useEffect(
    () => () => {
      speechRecognitionRef.current?.abort();
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    },
    [],
  );

  const addFiles = async (files: FileList | null) => {
    if (!files) return;
    setLocalError(null);
    const selectedFiles = Array.from(files);
    if (attachments.length + selectedFiles.length > 10) {
      setLocalError("파일은 한 번에 최대 10개까지 올릴 수 있어요.");
      return;
    }

    const invalidFile = selectedFiles.find((file) => {
      const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
      return !supportedExtensions.has(extension) || file.size > maxFileSize;
    });
    if (invalidFile) {
      const extension = invalidFile.name.split(".").pop()?.toUpperCase() ?? "파일";
      setLocalError(
        invalidFile.size > maxFileSize
          ? `${invalidFile.name} 파일은 10MB를 초과해요.`
          : `${extension} 형식은 지원하지 않아요. 텍스트, 문서, 음성 파일을 올려 주세요.`,
      );
      return;
    }

    try {
      const pendingFiles = await Promise.all(
        selectedFiles.map(async (file) => ({
          id: crypto.randomUUID(),
          name: file.name,
          extension: file.name.split(".").pop()?.toLowerCase() ?? "file",
          mimeType: file.type || "application/octet-stream",
          contentBase64: await readFileAsBase64(file),
          sizeLabel: formatSize(file.size),
        })),
      );
      onAttachmentsChange((current) => [...current, ...pendingFiles]);
    } catch {
      setLocalError("파일을 읽지 못했어요. 다른 파일로 다시 시도해 주세요.");
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const startRecording = async () => {
    setLocalError(null);
    setLiveTranscript("");
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setLocalError("이 브라우저에서는 음성 녹음을 지원하지 않아요.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      audioChunksRef.current = [];
      const supportedMimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";
      const recorder = new MediaRecorder(stream, { mimeType: supportedMimeType });
      mediaRecorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) audioChunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: supportedMimeType });
        stream.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
        if (blob.size > 0) onTranscribeRecording(blob);
      };

      const SpeechRecognitionApi =
        window.SpeechRecognition ?? window.webkitSpeechRecognition;
      if (SpeechRecognitionApi) {
        const recognition = new SpeechRecognitionApi();
        recognition.lang = "ko-KR";
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.onresult = (event) => {
          const transcriptParts: string[] = [];
          for (let index = event.resultIndex; index < event.results.length; index += 1) {
            transcriptParts.push(event.results[index][0]?.transcript ?? "");
          }
          setLiveTranscript(transcriptParts.join(" ").trim());
        };
        recognition.onerror = (event) => {
          if (event.error !== "aborted" && event.error !== "no-speech") {
            setLiveTranscript("");
          }
        };
        speechRecognitionRef.current = recognition;
        recognition.start();
      }

      recorder.start(1_000);
      setIsRecording(true);
    } catch {
      setLocalError("마이크 권한을 확인한 뒤 다시 시도해 주세요.");
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
  };

  const stopRecording = () => {
    speechRecognitionRef.current?.stop();
    speechRecognitionRef.current = null;
    mediaRecorderRef.current?.stop();
    mediaRecorderRef.current = null;
    setIsRecording(false);
    setLiveTranscript("");
  };

  return (
    <main className="flex min-h-[calc(100vh-72px)] min-w-0 flex-col bg-white/70 px-8 pb-3.5 max-[1180px]:px-5 max-[720px]:px-3.5">
      <header className="flex h-[78px] shrink-0 items-center justify-between gap-2 border-b border-[#f0edf5]">
        <div>
          <h1 className="m-0 text-lg font-bold tracking-[-0.02em]">
            {activeConversation?.title ?? "새로운 업무 정리"}
          </h1>
          <p className="mb-0 mt-1 text-[11px] text-[#9892aa]">
            긴 지시, 회의 기록, 문서, 음성을 실행 가능한 업무로 정리해요.
          </p>
        </div>
      </header>

      <section className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto grid max-w-[760px] gap-[26px] py-6 pb-7">
          {messages.length > 0 ? (
            messages.map((chatMessage) => (
              <MessageBubble key={chatMessage.id} message={chatMessage} />
            ))
          ) : (
            <div className="grid min-h-[360px] place-content-center gap-4 text-center text-[#8f899e]">
              <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-[#f2edff] text-3xl text-[#8652ec]">
                <i className="fa-solid fa-list-check" />
              </div>
              <strong className="text-lg text-[#2a2540]">업무 지시를 그대로 남겨 봐</strong>
              <span className="mx-auto max-w-md text-xs leading-6">
                텍스트를 입력하거나 문서·음성을 올리면 핵심 목표, 작업 순서, 담당자,
                기한, 확인 사항을 분리해 줄게.
              </span>
            </div>
          )}
          <div ref={scrollAnchorRef} />
        </div>
      </section>

      <section
        className="mx-auto mt-auto w-full max-w-[760px] rounded-[15px] border border-[#dedbe8] bg-white px-[15px] py-[13px] shadow-[0_12px_35px_rgba(53,41,91,0.07)]"
        aria-label="메시지 작성"
      >
        {attachments.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {attachments.map((file) => (
              <span
                className="inline-flex max-w-full items-center gap-2 rounded-lg bg-[#f5f1ff] px-3 py-2 text-xs"
                key={file.id}
              >
                <i className="fa-regular fa-file" />
                <span className="max-w-64 overflow-hidden text-ellipsis whitespace-nowrap">
                  {file.name}
                </span>
                <small>{file.sizeLabel}</small>
                <button
                  className="border-0 bg-transparent"
                  type="button"
                  onClick={() =>
                    onAttachmentsChange((current) =>
                      current.filter((item) => item.id !== file.id),
                    )
                  }
                  aria-label={`${file.name} 제거`}
                >
                  <i className="fa-solid fa-xmark" />
                </button>
              </span>
            ))}
          </div>
        )}
        {isRecording && liveTranscript && (
          <div className="mb-2 rounded-lg bg-[#f5f1ff] px-3 py-2 text-xs leading-5 text-[#6f42d7]">
            <i className="fa-solid fa-wave-square mr-2" />
            실시간 인식: {liveTranscript}
          </div>
        )}
        <textarea
          className="min-h-[82px] w-full resize-none border-0 bg-transparent text-[#252039] outline-none"
          value={message}
          onChange={(event) => onMessageChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              if (canSubmit && !isSubmitting) onSubmit();
            }
          }}
          placeholder="업무 지시, 회의 내용, 질문을 입력하세요..."
          rows={3}
          maxLength={12_000}
        />
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <input
              ref={fileInputRef}
              className="hidden"
              type="file"
              multiple
              accept=".txt,.md,.csv,.json,.xml,.yaml,.yml,.py,.js,.jsx,.ts,.tsx,.html,.css,.sql,.java,.c,.cpp,.h,.log,.pdf,.docx,.mp3,.mp4,.mpeg,.mpga,.m4a,.ogg,.wav,.webm,.flac"
              onChange={(event) => void addFiles(event.target.files)}
            />
            <button
              type="button"
              className="rounded-lg border border-[#e3e0eb] bg-white px-[11px] py-[9px] text-[11px]"
              onClick={() => fileInputRef.current?.click()}
            >
              <i className="fa-solid fa-paperclip mr-1.5" />파일
            </button>
            <button
              type="button"
              className={`rounded-lg border px-[11px] py-[9px] text-[11px] ${
                isRecording
                  ? "border-[#f0a6b8] bg-[#fff1f4] text-[#a53c57]"
                  : "border-[#e3e0eb] bg-white"
              }`}
              onClick={isRecording ? stopRecording : () => void startRecording()}
              disabled={isTranscribing}
            >
              <i
                className={`${
                  isTranscribing
                    ? "fa-solid fa-spinner fa-spin"
                    : isRecording
                      ? "fa-solid fa-stop"
                      : "fa-solid fa-microphone"
                } mr-1.5`}
              />
              {isTranscribing ? "변환 중" : isRecording ? "녹음 종료" : "음성"}
            </button>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-[10px] text-[#aaa5b7]">{message.length.toLocaleString()} / 12,000</span>
            <button
              className="h-11 w-11 shrink-0 rounded-[10px] border-0 bg-gradient-to-br from-[#9c64ff] to-[#6b38eb] text-white shadow-[0_8px_18px_rgba(108,57,235,0.24)] disabled:cursor-not-allowed disabled:opacity-45"
              type="button"
              disabled={!canSubmit || isSubmitting || isTranscribing}
              onClick={onSubmit}
              aria-label="메시지 보내기"
            >
              <i className={isSubmitting ? "fa-solid fa-spinner fa-spin" : "fa-solid fa-paper-plane"} />
            </button>
          </div>
        </div>
      </section>
      {(localError || errorMessage) && (
        <p className="mx-auto mt-2.5 rounded-lg bg-[#f7f2ff] px-3 py-2 text-center text-[11px] text-[#6f42d7]">
          {localError ?? errorMessage}
        </p>
      )}
      <p className="mx-auto mt-2.5 text-center text-[11px] text-[#9a96aa]">
        중요한 내용은 한번 더 확인해 주세요.
      </p>
    </main>
  );
}