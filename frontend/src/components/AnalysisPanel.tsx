import { useMemo, useState } from "react";

import { analysisTabs, type AnalysisTabId } from "../config/ui";
import type { AnalysisResult, Priority, SourceFile } from "../types/workspace";

interface AnalysisPanelProps {
  analysis: AnalysisResult | null;
  sourceFiles: SourceFile[];
  onToggleChecklist: (itemId: string, completed: boolean) => void;
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

function DetailList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) {
    return null;
  }

  return (
    <section className={cardClass}>
      <h2 className={headingClass}>{title}</h2>
      <ul className="mt-4 grid list-disc gap-2 pl-[18px] text-[13px] leading-[1.6]">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

export function AnalysisPanel({
  analysis,
  sourceFiles,
  onToggleChecklist,
}: AnalysisPanelProps) {
  const [activeTab, setActiveTab] = useState<AnalysisTabId>("analysis");
  const completedCount = useMemo(
    () => analysis?.tasks.filter((item) => item.completed).length ?? 0,
    [analysis],
  );

  return (
    <aside className="min-w-0 border-l border-[#e9e7f3] bg-white/90 px-[18px] pb-[18px] max-[960px]:col-span-full max-[960px]:border-l-0 max-[960px]:border-t max-[720px]:px-3.5">
      <div className="grid h-[62px] grid-cols-3 border-b border-[#e4e1ed]" role="tablist">
        {analysisTabs.map((tab) => (
          <button
            className={`relative border-0 bg-transparent font-semibold ${activeTab === tab.id ? "text-[#7b49e8] after:absolute after:bottom-[-1px] after:left-3 after:right-3 after:h-0.5 after:rounded-sm after:bg-[#7a49ea] after:content-['']" : "text-[#5f596d]"}`}
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

      <div className="grid min-h-0 gap-4 overflow-y-auto py-[18px]">
        {activeTab === "analysis" &&
          (analysis ? (
            <>
              <section className={cardClass}>
                <h2 className={headingClass}>
                  <i className="fa-regular fa-star text-[#8050eb]" />핵심 목표
                </h2>
                <p className="mt-4 text-[13px] leading-[1.7]">{analysis.core_goal}</p>
              </section>

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
                    <li className="rounded-lg border border-[#ece9f3] p-3" key={task.id}>
                      <label className="flex items-start gap-2.5">
                        <input
                          className="mt-0.5 h-[17px] w-[17px] accent-[#8050e9]"
                          type="checkbox"
                          checked={task.completed ?? false}
                          onChange={(event) => onToggleChecklist(task.id, event.target.checked)}
                        />
                        <span className="min-w-0 flex-1">
                          <strong className="block text-[13px]">
                            {task.order}. {task.title}
                          </strong>
                          {task.description && (
                            <span className="mt-1 block text-xs leading-[1.5] text-[#6f697d]">
                              {task.description}
                            </span>
                          )}
                        </span>
                      </label>
                      <div className="mt-3 flex flex-wrap gap-1.5 text-[10px]">
                        <span className="rounded-full bg-[#f2effa] px-2 py-1">
                          우선순위 {priorityLabels[task.priority]}
                        </span>
                        {task.deadline && (
                          <span className="rounded-full bg-[#fff2df] px-2 py-1">기한 {task.deadline}</span>
                        )}
                        {task.assignee && (
                          <span className="rounded-full bg-[#edf5ff] px-2 py-1">담당 {task.assignee}</span>
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
                        <dd className="m-0 mt-1 leading-[1.6] text-[#6f697d]">{item.explanation}</dd>
                      </div>
                    ))}
                  </dl>
                </section>
              )}
            </>
          ) : (
            <div className="grid min-h-[360px] place-content-center place-items-center gap-[13px] rounded-[14px] border border-dashed border-[#d9d4e7] bg-white/65 p-7 text-center text-[#8f899e]">
              <i className="fa-solid fa-wand-magic-sparkles text-3xl text-[#8652ec]" />
              <h2 className="m-0 text-[17px] text-[#2a2540]">분석 결과가 여기에 표시돼요</h2>
              <p className="m-0 text-xs leading-[1.6]">업무 지시를 보내면 실행 가능한 체크리스트로 정리해요.</p>
            </div>
          ))}

        {activeTab === "sources" && (
          <section className={cardClass}>
            <h2 className={headingClass}>소스 파일</h2>
            {sourceFiles.length > 0 ? (
              <ul className="mt-4 grid gap-2">
                {sourceFiles.map((file) => (
                  <li key={file.id}>{file.name}</li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-[#9994a8]">연결된 소스 파일이 없어요.</p>
            )}
          </section>
        )}

        {activeTab === "notes" && (
          <section className={cardClass}>
            <h2 className={headingClass}>노트</h2>
            <textarea
              className="mt-4 min-h-[260px] w-full resize-y rounded-[9px] border border-[#e3e0eb] p-3 outline-none"
              placeholder="분석 결과에 대한 메모를 작성하세요."
            />
          </section>
        )}
      </div>
    </aside>
  );
}
