import { useMemo, useState } from "react";
import { analysisTabs, type AnalysisTabId } from "../config/ui";
import type { AnalysisResult, SourceFile } from "../types/workspace";

interface AnalysisPanelProps {
  analysis: AnalysisResult | null;
  sourceFiles: SourceFile[];
  onToggleChecklist: (itemId: string, completed: boolean) => void;
}

const cardClass = "rounded-[13px] border border-[#e1deeb] bg-white p-5 shadow-[0_10px_28px_rgba(58,43,97,0.035)]";
const headingClass = "m-0 flex items-center gap-[9px] text-base font-bold";

export function AnalysisPanel({ analysis, sourceFiles, onToggleChecklist }: AnalysisPanelProps) {
  const [activeTab, setActiveTab] = useState<AnalysisTabId>("analysis");
  const completedCount = useMemo(() => analysis?.checklist.filter((item) => item.completed).length ?? 0, [analysis]);

  return (
    <aside className="min-w-0 border-l border-[#e9e7f3] bg-white/90 px-[18px] pb-[18px] max-[960px]:col-span-full max-[960px]:border-l-0 max-[960px]:border-t max-[720px]:px-3.5">
      <div className="grid h-[62px] grid-cols-3 border-b border-[#e4e1ed]" role="tablist">
        {analysisTabs.map((tab) => (
          <button className={`relative border-0 bg-transparent font-semibold ${activeTab === tab.id ? "text-[#7b49e8] after:absolute after:bottom-[-1px] after:left-3 after:right-3 after:h-0.5 after:rounded-sm after:bg-[#7a49ea] after:content-['']" : "text-[#5f596d]"}`} type="button" role="tab" aria-selected={activeTab === tab.id} key={tab.id} onClick={() => setActiveTab(tab.id)}>{tab.label}</button>
        ))}
      </div>

      <div className="grid min-h-0 gap-4 overflow-y-auto py-[18px]">
        {activeTab === "analysis" && (analysis ? (
          <>
            <section className={cardClass}>
              <h2 className={headingClass}><i className="fa-regular fa-star text-[#8050eb]" />핵심 요약</h2>
              {analysis.summary.length > 0 ? <ul className="mt-5 grid list-disc gap-3 pl-[18px]">{analysis.summary.map((item) => <li className="text-[13px] leading-[1.6]" key={item}>{item}</li>)}</ul> : <p className="mx-2 my-1 text-xs text-[#9994a8]">요약 결과가 없어요.</p>}
            </section>

            <section className={cardClass}>
              <div className="flex items-center justify-between">
                <h2 className={headingClass}><i className="fa-regular fa-square-check text-[#8050eb]" />체크리스트</h2>
                <span className="text-xs text-[#777187]">{completedCount} / {analysis.checklist.length} 완료</span>
              </div>
              {analysis.checklist.length > 0 ? (
                <ul className="mt-[19px] grid list-none gap-[13px] p-0">
                  {analysis.checklist.map((item) => (
                    <li className="flex items-center justify-between gap-2.5" key={item.id}>
                      <label className="flex min-w-0 items-center gap-2.5"><input className="h-[17px] w-[17px] accent-[#8050e9]" type="checkbox" checked={item.completed} onChange={(event) => onToggleChecklist(item.id, event.target.checked)} /><span className="text-[13px]">{item.content}</span></label>
                      {item.dueLabel && <small className="shrink-0 rounded-full bg-[#f2effa] px-2 py-1 text-[10px] text-[#7058a5]">{item.dueLabel}</small>}
                    </li>
                  ))}
                </ul>
              ) : <p className="mx-2 my-1 text-xs text-[#9994a8]">생성된 체크리스트가 없어요.</p>}
              <button className="mt-5 w-[calc(100%-42px)] rounded-lg border border-[#e3e0eb] bg-white p-2.5" type="button"><i className="fa-solid fa-download mr-[7px]" />체크리스트 내보내기</button>
            </section>

            {analysis.nextStep && (
              <section className={`${cardClass} grid gap-3.5`}>
                <h2 className={headingClass}><i className="fa-regular fa-lightbulb text-[#f2aa26]" />다음 단계 추천</h2>
                <p className="m-0 text-[13px]">{analysis.nextStep}</p>
                <button className="w-[70%] justify-self-center rounded-lg border border-[#e3e0eb] bg-[#f7f3ff] p-[11px] font-bold text-[#7b4bea]" type="button"><i className="fa-regular fa-calendar mr-[7px]" />캘린더에 추가</button>
              </section>
            )}
          </>
        ) : (
          <div className="grid min-h-[360px] place-content-center place-items-center gap-[13px] rounded-[14px] border border-dashed border-[#d9d4e7] bg-white/65 p-7 text-center text-[#8f899e]">
            <i className="fa-solid fa-wand-magic-sparkles text-3xl text-[#8652ec]" /><h2 className="m-0 text-[17px] text-[#2a2540]">분석 결과가 여기에 표시돼요</h2><p className="m-0 text-xs leading-[1.6]">업무 지시나 파일을 보내면 요약과 체크리스트를 만들어드려요.</p>
          </div>
        ))}

        {activeTab === "sources" && (
          <section className={cardClass}>
            <h2 className={headingClass}><i className="fa-regular fa-folder-open text-[#8050eb]" />소스 파일</h2>
            {sourceFiles.length > 0 ? <ul className="mt-[18px] grid list-none gap-2.5 p-0">{sourceFiles.map((file) => <li className="flex items-center gap-[9px] rounded-lg bg-[#f8f6fc] p-2.5" key={file.id}><i className="fa-regular fa-file-lines" /><span>{file.name}</span></li>)}</ul> : <p className="mx-2 my-1 text-xs text-[#9994a8]">연결된 소스 파일이 없어요.</p>}
          </section>
        )}

        {activeTab === "notes" && (
          <section className={cardClass}>
            <h2 className={headingClass}><i className="fa-regular fa-note-sticky text-[#8050eb]" />노트</h2>
            <textarea className="mt-4 min-h-[260px] w-full resize-y rounded-[9px] border border-[#e3e0eb] p-3 outline-none" placeholder="분석 결과에 대한 메모를 작성하세요." />
          </section>
        )}
      </div>
    </aside>
  );
}
