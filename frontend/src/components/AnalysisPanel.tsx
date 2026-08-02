import { useMemo, useState } from "react";

import { resolveDownloadUrl } from "../api/taskApi";
import { analysisTabs, type AnalysisTabId } from "../config/ui";
import type {
  AnalysisResult,
  Priority,
  ReminderSummary,
  SourceFile,
  TaskItem,
  TaskStatus,
  TaskUpdatePayload,
} from "../types/workspace";

interface AnalysisPanelProps {
  activeConversationId: string | null;
  analysis: AnalysisResult | null;
  sourceFiles: SourceFile[];
  notes: string;
  reminders: ReminderSummary[];
  onChangeTask: (taskId: string, changes: TaskUpdatePayload) => Promise<boolean>;
  onRemoveTask: (taskId: string) => void;
  onNotesChange: (content: string) => void;
  onSaveNotes: () => Promise<boolean>;
  onAddReminder: (
    taskId: string | undefined,
    message: string,
    remindAt: string,
  ) => Promise<boolean>;
}

const cardClass =
  "rounded-[13px] border border-[#e1deeb] bg-white p-5 shadow-[0_10px_28px_rgba(58,43,97,0.035)]";
const headingClass = "m-0 flex items-center gap-[9px] text-base font-bold";

const priorityLabels: Record<Priority, string> = {
  urgent: "긴급",
  high: "높음",
  normal: "보통",
  low: "낮음",
  unspecified: "미지정",
};

const statusLabels: Record<TaskStatus, string> = {
  todo: "대기",
  in_progress: "진행 중",
  done: "완료",
};

// 문자열 목록을 제목이 있는 상세 카드로 표시한다.
function DetailList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <section className={cardClass}>
      <h2 className={headingClass}>{title}</h2>
      <ul className="mt-4 grid list-disc gap-2 pl-[18px] text-[13px] leading-[1.6]">
        {items.map((item, index) => (
          <li key={`${item}-${index}`}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

// 체크리스트 업무의 세부 내용을 편집하는 입력 화면을 표시한다.
function TaskEditor({
  task,
  onSave,
  onCancel,
}: {
  task: TaskItem;
  onSave: (changes: TaskUpdatePayload) => Promise<void>;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState(task.title);
  const [description, setDescription] = useState(task.description ?? "");
  const [priority, setPriority] = useState<Priority>(task.priority);
  const [deadline, setDeadline] = useState(task.deadline ?? "");
  const [assignee, setAssignee] = useState(task.assignee ?? "");
  const [submissionTarget, setSubmissionTarget] = useState(task.submission_target ?? "");
  const [completionCondition, setCompletionCondition] = useState(task.completion_condition ?? "");

  return (
    <div className="mt-3 grid gap-2 rounded-lg bg-[#faf9fd] p-3">
      <input
        className="rounded-lg border border-[#ded9e9] px-3 py-2 text-xs outline-none focus:border-[#8351e8]"
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        placeholder="작업 제목"
      />
      <textarea
        className="min-h-20 rounded-lg border border-[#ded9e9] px-3 py-2 text-xs outline-none focus:border-[#8351e8]"
        value={description}
        onChange={(event) => setDescription(event.target.value)}
        placeholder="세부 설명"
      />
      <div className="grid grid-cols-2 gap-2">
        <select
          className="rounded-lg border border-[#ded9e9] bg-white px-2 py-2 text-xs"
          value={priority}
          onChange={(event) => setPriority(event.target.value as Priority)}
        >
          {Object.entries(priorityLabels).map(([value, label]) => (
            <option value={value} key={value}>{label}</option>
          ))}
        </select>
        <input
          className="rounded-lg border border-[#ded9e9] px-3 py-2 text-xs"
          value={deadline}
          onChange={(event) => setDeadline(event.target.value)}
          placeholder="기한"
        />
        <input
          className="rounded-lg border border-[#ded9e9] px-3 py-2 text-xs"
          value={assignee}
          onChange={(event) => setAssignee(event.target.value)}
          placeholder="담당자"
        />
        <input
          className="rounded-lg border border-[#ded9e9] px-3 py-2 text-xs"
          value={submissionTarget}
          onChange={(event) => setSubmissionTarget(event.target.value)}
          placeholder="제출 대상"
        />
      </div>
      <input
        className="rounded-lg border border-[#ded9e9] px-3 py-2 text-xs"
        value={completionCondition}
        onChange={(event) => setCompletionCondition(event.target.value)}
        placeholder="완료 조건"
      />
      <div className="flex justify-end gap-2">
        <button
          className="rounded-lg border border-[#ded9e9] bg-white px-3 py-2 text-xs"
          type="button"
          onClick={onCancel}
        >
          취소
        </button>
        <button
          className="rounded-lg border-0 bg-[#7546e5] px-3 py-2 text-xs font-bold text-white"
          type="button"
          disabled={!title.trim()}
          onClick={() =>
            void onSave({
              title: title.trim(),
              description: description.trim() || null,
              priority,
              deadline: deadline.trim() || null,
              assignee: assignee.trim() || null,
              submission_target: submissionTarget.trim() || null,
              completion_condition: completionCondition.trim() || null,
            })
          }
        >
          저장
        </button>
      </div>
    </div>
  );
}

// 분석 결과와 체크리스트 및 메모와 예약 설정 화면을 표시한다.
export function AnalysisPanel({
  activeConversationId,
  analysis,
  sourceFiles,
  notes,
  reminders,
  onChangeTask,
  onRemoveTask,
  onNotesChange,
  onSaveNotes,
  onAddReminder,
}: AnalysisPanelProps) {
  const [activeTab, setActiveTab] = useState<AnalysisTabId>("analysis");
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null);
  const [reminderTaskId, setReminderTaskId] = useState("");
  const [reminderMessage, setReminderMessage] = useState("");
  const [reminderAt, setReminderAt] = useState("");
  const [notesSaved, setNotesSaved] = useState(false);

  const completedCount = useMemo(
    () => analysis?.tasks.filter((item) => item.status === "done").length ?? 0,
    [analysis],
  );
  const progress = analysis?.tasks.length
    ? Math.round((completedCount / analysis.tasks.length) * 100)
    : 0;

  // 현재 대화의 메모를 저장하고 완료 상태를 잠시 표시한다.
  const saveNotes = async () => {
    const saved = await onSaveNotes();
    if (!saved) return;
    setNotesSaved(true);
    window.setTimeout(() => setNotesSaved(false), 1_500);
  };

  // 입력한 문구와 예약 시각으로 새 업무 알림을 저장한다.
  const submitReminder = async () => {
    if (!reminderMessage.trim() || !reminderAt) return;
    const saved = await onAddReminder(
      reminderTaskId || undefined,
      reminderMessage.trim(),
      new Date(reminderAt).toISOString(),
    );
    if (!saved) return;
    setReminderMessage("");
    setReminderAt("");
  };

  return (
    <aside className="min-w-0 border-l border-[#e9e7f3] bg-white/90 px-[18px] pb-[18px] max-[960px]:col-span-full max-[960px]:border-l-0 max-[960px]:border-t max-[720px]:px-3.5">
      <div className="grid h-[62px] grid-cols-3 border-b border-[#e4e1ed]" role="tablist">
        {analysisTabs.map((tab) => (
          <button
            className={`relative border-0 bg-transparent font-semibold ${
              activeTab === tab.id
                ? "text-[#7b49e8] after:absolute after:bottom-[-1px] after:left-3 after:right-3 after:h-0.5 after:rounded-sm after:bg-[#7a49ea] after:content-['']"
                : "text-[#5f596d]"
            }`}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="grid max-h-[calc(100vh-152px)] min-h-0 gap-4 overflow-y-auto py-[18px] max-[960px]:max-h-none">
        {activeTab === "analysis" &&
          (analysis ? (
            <>
              {analysis.summary && (
                <section className={cardClass}>
                  <h2 className={headingClass}>
                    <i className="fa-regular fa-file-lines text-[#8050eb]" />전체 요약
                  </h2>
                  <p className="mt-4 whitespace-pre-wrap text-[13px] leading-[1.7]">
                    {analysis.summary}
                  </p>
                </section>
              )}

              <section className={cardClass}>
                <h2 className={headingClass}>
                  <i className="fa-regular fa-star text-[#8050eb]" />핵심 목표
                </h2>
                <p className="mt-4 text-[13px] leading-[1.7]">{analysis.core_goal}</p>
                <div className="mt-4">
                  <div className="mb-2 flex items-center justify-between text-[11px] text-[#777187]">
                    <span>업무 진행률</span>
                    <strong>{progress}%</strong>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-[#eeeaf5]">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-[#9b68f6] to-[#7042e3] transition-[width]"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                </div>
              </section>

              <DetailList title="핵심 내용" items={analysis.key_points} />
              <DetailList title="확정된 결정" items={analysis.decisions} />

              <section className={cardClass}>
                <div className="flex items-center justify-between">
                  <h2 className={headingClass}>
                    <i className="fa-regular fa-square-check text-[#8050eb]" />체크리스트
                  </h2>
                  <span className="text-xs text-[#777187]">
                    {completedCount} / {analysis.tasks.length} 완료
                  </span>
                </div>
                <ul className="mt-[19px] grid list-none gap-[14px] p-0">
                  {analysis.tasks.map((task) => (
                    <li className="rounded-xl border border-[#ece9f3] p-3" key={task.id}>
                      <div className="flex items-start gap-2.5">
                        <input
                          className="mt-0.5 h-[17px] w-[17px] accent-[#8050e9]"
                          type="checkbox"
                          checked={task.status === "done"}
                          onChange={(event) =>
                            onChangeTask(task.id, {
                              status: event.target.checked ? "done" : "todo",
                            })
                          }
                          aria-label={`${task.title} 완료 상태`}
                        />
                        <div className="min-w-0 flex-1">
                          <strong className={`block text-[13px] ${task.status === "done" ? "text-[#8d8799] line-through" : ""}`}>
                            {task.order}. {task.title}
                          </strong>
                          {task.description && (
                            <span className="mt-1 block text-xs leading-[1.5] text-[#6f697d]">
                              {task.description}
                            </span>
                          )}
                        </div>
                        <button
                          className="grid h-7 w-7 place-items-center rounded-lg border-0 bg-[#f5f1fb] text-[#7250b7]"
                          type="button"
                          aria-label={`${task.title} 수정`}
                          onClick={() =>
                            setEditingTaskId((current) => (current === task.id ? null : task.id))
                          }
                        >
                          <i className="fa-solid fa-pen text-[10px]" />
                        </button>
                        <button
                          className="grid h-7 w-7 place-items-center rounded-lg border-0 bg-[#fff1f4] text-[#a74660]"
                          type="button"
                          aria-label={`${task.title} 삭제`}
                          onClick={() => {
                            if (window.confirm("이 작업을 체크리스트에서 삭제할까요?")) {
                              onRemoveTask(task.id);
                            }
                          }}
                        >
                          <i className="fa-regular fa-trash-can text-[10px]" />
                        </button>
                      </div>

                      <div className="mt-3 flex flex-wrap items-center gap-1.5 text-[10px]">
                        <select
                          className="rounded-full border-0 bg-[#edf5ff] px-2 py-1"
                          value={task.status}
                          onChange={(event) =>
                            onChangeTask(task.id, { status: event.target.value as TaskStatus })
                          }
                          aria-label={`${task.title} 진행 상태`}
                        >
                          {Object.entries(statusLabels).map(([value, label]) => (
                            <option value={value} key={value}>{label}</option>
                          ))}
                        </select>
                        <span className="rounded-full bg-[#f2effa] px-2 py-1">
                          우선순위 {priorityLabels[task.priority]}
                        </span>
                        {task.deadline && (
                          <span className="rounded-full bg-[#fff2df] px-2 py-1">
                            기한 {task.deadline}
                          </span>
                        )}
                        {task.assignee && (
                          <span className="rounded-full bg-[#edf5ff] px-2 py-1">
                            담당 {task.assignee}
                          </span>
                        )}
                      </div>
                      {task.dependencies.length > 0 && (
                        <p className="mb-0 mt-2 text-[11px] text-[#6f697d]">
                          선행 업무: {task.dependencies.join(", ")}
                        </p>
                      )}
                      {task.submission_target && (
                        <p className="mb-0 mt-2 text-[11px] text-[#6f697d]">
                          제출 대상: {task.submission_target}
                        </p>
                      )}
                      {task.completion_condition && (
                        <p className="mb-0 mt-2 text-[11px] text-[#6f697d]">
                          완료 조건: {task.completion_condition}
                        </p>
                      )}
                      {editingTaskId === task.id && (
                        <TaskEditor
                          task={task}
                          onCancel={() => setEditingTaskId(null)}
                          onSave={async (changes) => {
                            const saved = await onChangeTask(task.id, changes);
                            if (saved) setEditingTaskId(null);
                          }}
                        />
                      )}
                    </li>
                  ))}
                </ul>
              </section>

              <DetailList title="확인이 필요한 내용" items={analysis.confirmation_items} />
              <DetailList title="누락되거나 애매한 지시" items={analysis.ambiguities} />

              {analysis.difficult_terms.length > 0 && (
                <section className={cardClass}>
                  <h2 className={headingClass}>어려운 용어</h2>
                  <dl className="mt-4 grid gap-3 text-[13px]">
                    {analysis.difficult_terms.map((item) => (
                      <div key={item.term}>
                        <dt className="font-bold">{item.term}</dt>
                        <dd className="m-0 mt-1 leading-[1.6] text-[#6f697d]">
                          {item.explanation}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </section>
              )}

              <section className={cardClass}>
                <h2 className={headingClass}>
                  <i className="fa-regular fa-bell text-[#8050eb]" />업무 알림
                </h2>
                <div className="mt-4 grid gap-2">
                  <select
                    className="rounded-lg border border-[#ded9e9] bg-white px-3 py-2 text-xs"
                    value={reminderTaskId}
                    onChange={(event) => setReminderTaskId(event.target.value)}
                  >
                    <option value="">전체 업무 알림</option>
                    {analysis.tasks.map((task) => (
                      <option value={task.id} key={task.id}>{task.order}. {task.title}</option>
                    ))}
                  </select>
                  <input
                    className="rounded-lg border border-[#ded9e9] px-3 py-2 text-xs"
                    value={reminderMessage}
                    onChange={(event) => setReminderMessage(event.target.value)}
                    placeholder="알림 문구"
                  />
                  <input
                    className="rounded-lg border border-[#ded9e9] px-3 py-2 text-xs"
                    type="datetime-local"
                    value={reminderAt}
                    onChange={(event) => setReminderAt(event.target.value)}
                  />
                  <button
                    className="rounded-lg border-0 bg-[#7546e5] px-3 py-2 text-xs font-bold text-white disabled:opacity-40"
                    type="button"
                    disabled={!reminderMessage.trim() || !reminderAt || !activeConversationId}
                    onClick={() => void submitReminder()}
                  >
                    알림 저장
                  </button>
                </div>
                {reminders.length > 0 && (
                  <ul className="mt-4 grid gap-2 p-0 text-[11px]">
                    {reminders.map((reminder) => (
                      <li className="rounded-lg bg-[#f8f6fc] p-2" key={reminder.id}>
                        <strong className="block">{reminder.message}</strong>
                        <span className="mt-1 block text-[#7c7588]">
                          {new Date(reminder.remindAt).toLocaleString("ko-KR")} · {reminder.status}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </>
          ) : (
            <div className="grid min-h-[360px] place-content-center place-items-center gap-[13px] rounded-[14px] border border-dashed border-[#d9d4e7] bg-white/65 p-7 text-center text-[#8f899e]">
              <i className="fa-solid fa-wand-magic-sparkles text-3xl text-[#8652ec]" />
              <h2 className="m-0 text-[17px] text-[#2a2540]">분석 결과가 여기에 표시돼요</h2>
              <p className="m-0 text-xs leading-[1.6]">
                업무 지시를 보내면 실행 가능한 체크리스트로 정리해요.
              </p>
            </div>
          ))}

        {activeTab === "sources" && (
          <section className={cardClass}>
            <h2 className={headingClass}>현재 대화의 소스 파일</h2>
            {sourceFiles.length > 0 ? (
              <ul className="mt-4 grid gap-2 p-0">
                {sourceFiles.map((file) => (
                  <li className="rounded-lg border border-[#ece9f3] p-3" key={file.id}>
                    <a
                      className="flex items-center justify-between gap-2 text-xs text-[#4f4860] no-underline"
                      href={resolveDownloadUrl(file.downloadUrl)}
                      download={file.name}
                    >
                      <span className="min-w-0 overflow-hidden text-ellipsis whitespace-nowrap">
                        <i className="fa-regular fa-file mr-2 text-[#8050eb]" />{file.name}
                      </span>
                      <i className="fa-solid fa-download" />
                    </a>
                    <small className="mt-1 block text-[#9892aa]">
                      {file.extension.toUpperCase()} · {file.sizeLabel} · {file.uploadedAt}
                    </small>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-[#9994a8]">현재 대화에 연결된 파일이 없어요.</p>
            )}
          </section>
        )}

        {activeTab === "notes" && (
          <section className={cardClass}>
            <div className="flex items-center justify-between">
              <h2 className={headingClass}>업무 노트</h2>
              {notesSaved && <span className="text-[11px] text-[#7042df]">저장했어요</span>}
            </div>
            <textarea
              className="mt-4 min-h-[300px] w-full resize-y rounded-[9px] border border-[#e3e0eb] p-3 text-sm leading-6 outline-none focus:border-[#8351e8]"
              placeholder="분석 결과에 대한 메모를 작성하세요."
              value={notes}
              disabled={!activeConversationId}
              onChange={(event) => onNotesChange(event.target.value)}
            />
            <button
              className="mt-3 w-full rounded-lg border-0 bg-[#7546e5] px-3 py-2.5 text-xs font-bold text-white disabled:opacity-40"
              type="button"
              disabled={!activeConversationId}
              onClick={() => void saveNotes()}
            >
              노트 저장
            </button>
          </section>
        )}
      </div>
    </aside>
  );
}