"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, ChevronRight, CircleDashed, Layers3 } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export function MaterialProjectSwitcher({ basePath = "/materials" }: { basePath?: string }) {
  const searchParams = useSearchParams();
  const currentId = searchParams.get("program") ?? "";
  const packages = useQuery({ queryKey: ["application-packages"], queryFn: api.applicationPackages });
  const rows = packages.data ?? [];
  const readyCount = rows.filter((item) => item.ready).length;
  const inProgressCount = rows.filter((item) => !item.ready && item.checklist.some((row) => row.status === "ready")).length;

  return <section className="mb-6 overflow-hidden rounded-[28px] border border-black/5 bg-white/85 shadow-soft backdrop-blur">
    <div className="relative overflow-hidden border-b border-black/5 px-5 py-5 sm:px-6">
      <div className="pointer-events-none absolute -right-10 -top-20 size-52 rounded-full bg-mint/60 blur-3xl" />
      <div className="relative flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <span className="grid size-11 place-items-center rounded-2xl bg-ink text-emerald-300 shadow-soft"><Layers3 size={19} /></span>
          <div><div className="flex flex-wrap items-center gap-2"><h2 className="text-lg font-black">全部申请项目</h2>{rows.length > 0 && <span className="rounded-full bg-paper px-2.5 py-1 text-[11px] font-black text-ink/45">{rows.length} 个项目</span>}</div><p className="mt-1 text-xs leading-5 text-ink/45">选择一个项目，在下方继续准备对应申请材料。</p></div>
        </div>
        <div className="flex items-center gap-4"><div className="hidden gap-4 text-right sm:flex"><div><strong className="block text-sm">{inProgressCount}</strong><span className="text-[10px] text-ink/40">准备中</span></div><div><strong className="block text-sm text-emerald-700">{readyCount}</strong><span className="text-[10px] text-ink/40">已就绪</span></div></div><Link href="/shortlist" className="inline-flex items-center gap-1 rounded-full border border-black/5 bg-white px-3 py-2 text-xs font-black text-moss transition hover:border-moss/25 hover:bg-mint/40">管理选校清单 <ChevronRight size={13} /></Link></div>
      </div>
    </div>
    <div className="grid gap-4 p-4 sm:grid-cols-2 sm:p-5 xl:grid-cols-3">
      {packages.data?.map((item) => {
        const completed = item.checklist.filter((row) => row.status === "ready").length;
        const total = item.checklist.length;
        const percent = total ? Math.round(completed / total * 100) : 0;
        const missing = item.checklist.filter((row) => row.status === "missing").length;
        const pending = item.checklist.filter((row) => row.status !== "ready" && row.status !== "missing").length;
        const active = item.program.id === currentId;
        return <Link aria-current={active ? "page" : undefined} key={item.id} href={`${basePath}?program=${item.program.id}`} className={cn("group flex min-h-[188px] flex-col rounded-2xl border p-4 transition duration-200", active ? "border-ink bg-ink text-white shadow-soft" : "border-black/5 bg-[#faf9f5] hover:-translate-y-0.5 hover:border-moss/25 hover:bg-white hover:shadow-soft")}>
          <div className="flex items-start justify-between gap-3"><div className="min-w-0"><div className="flex items-center gap-2"><p className={cn("truncate text-[10px] font-black uppercase tracking-[0.12em]", active ? "text-emerald-300" : "text-moss")}>{item.program.university}</p>{active && <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 text-[9px] font-black text-white/70">当前</span>}</div><p className="mt-2 line-clamp-2 min-h-10 text-sm font-black leading-5">{item.program.name}</p></div>{item.ready ? <CheckCircle2 className={active ? "text-emerald-300" : "text-emerald-600"} size={18} /> : <CircleDashed className={active ? "text-white/40" : "text-ink/25"} size={18} />}</div>
          <div className="mt-4 grid grid-cols-3 gap-2"><div className={cn("rounded-xl px-2.5 py-2", active ? "bg-white/8" : "bg-white")}><strong className="block text-sm">{completed}</strong><span className={cn("text-[10px]", active ? "text-white/45" : "text-ink/40")}>已完成</span></div><div className={cn("rounded-xl px-2.5 py-2", active ? "bg-white/8" : "bg-white")}><strong className={cn("block text-sm", active ? "text-amber-200" : "text-amber-700")}>{pending}</strong><span className={cn("text-[10px]", active ? "text-white/45" : "text-ink/40")}>待确认</span></div><div className={cn("rounded-xl px-2.5 py-2", active ? "bg-white/8" : "bg-white")}><strong className={cn("block text-sm", active ? "text-red-200" : "text-red-600")}>{missing}</strong><span className={cn("text-[10px]", active ? "text-white/45" : "text-ink/40")}>缺少</span></div></div>
          <div className="mt-4 flex items-center justify-between text-xs"><span className={active ? "text-white/55" : "text-ink/45"}>{item.ready ? "材料已就绪" : completed ? "准备中" : "未开始"}</span><strong>{completed}/{total}</strong></div>
          <div className={cn("mt-2 h-1.5 overflow-hidden rounded-full", active ? "bg-white/10" : "bg-black/5")}><div className={cn("h-full rounded-full transition-all", active ? "bg-emerald-300" : "bg-moss")} style={{ width: `${percent}%` }} /></div>
          <div className={cn("mt-auto flex items-center justify-end gap-1 pt-3 text-[11px] font-black", active ? "text-emerald-300" : "text-moss")}>{active ? "正在处理" : completed ? "继续准备" : "开始准备"}<ChevronRight size={12} /></div>
        </Link>;
      })}
      {packages.isLoading && [1, 2, 3].map((item) => <div key={item} className="h-[188px] animate-pulse rounded-2xl bg-paper" />)}
    </div>
    {!packages.isLoading && !rows.length && <div className="px-6 py-10 text-center"><p className="text-sm font-black">还没有申请项目</p><p className="mt-1 text-xs text-ink/45">先在选校清单中加入项目，再回来准备材料。</p><Link href="/programs" className="mt-4 inline-flex items-center gap-1 text-xs font-black text-moss">前往项目推荐 <ChevronRight size={13} /></Link></div>}
    {!currentId && rows.length > 0 && <div className="border-t border-black/5 bg-mint/25 px-5 py-3 text-center text-xs font-bold text-moss">请从上方选择一个项目，开始准备申请材料</div>}
  </section>;
}
