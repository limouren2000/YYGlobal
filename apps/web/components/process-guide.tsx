import { Check, Circle } from "lucide-react";
import { cn } from "@/lib/utils";

const steps = ["画像与初始材料", "项目推荐", "选校清单", "申请材料准备", "申请看板"];

export function ProcessGuide({ current, completed = [] }: { current: number; completed?: number[] }) {
  return <div className="mb-6 overflow-x-auto rounded-2xl border border-black/5 bg-white/65 p-4">
    <p className="mb-3 text-xs font-black uppercase tracking-[0.16em] text-moss">P0 申请流程 · 当前第 {current + 1} 步</p>
    <div className="flex min-w-[760px] items-center">
      {steps.map((step, index) => <div key={step} className="contents"><div className={cn("flex items-center gap-2 text-xs font-bold", index === current ? "text-moss" : completed.includes(index) ? "text-emerald-700" : "text-ink/35")}><span className={cn("grid size-7 place-items-center rounded-full border", index === current ? "border-moss bg-mint" : completed.includes(index) ? "border-emerald-200 bg-emerald-50" : "border-black/10 bg-white")}>{completed.includes(index) ? <Check size={14} /> : <Circle size={11} />}</span>{step}</div>{index < steps.length - 1 && <div className="mx-3 h-px min-w-8 flex-1 bg-black/10" />}</div>)}
    </div>
  </div>;
}
