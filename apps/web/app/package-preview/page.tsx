"use client";

import {
  ArrowLeft, Bot, Check, CheckCircle2, ChevronRight, CircleAlert, Clock3,
  FileText, FolderOpen, Link2, Plus, Save, Sparkles, Upload, UserRound, X,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type WritingKind = "CV" | "PS" | "推荐信";
type MaterialSlot = { id: string; kind: WritingKind; title: string; requirement: string };

const PREVIEW_STORAGE_KEY = "yyglobal-package-preview-georgia-tech";

const materialSlots: MaterialSlot[] = [
  { id: "cv", kind: "CV", title: "CV / Resume", requirement: "英文，建议 1–2 页" },
  { id: "sop", kind: "PS", title: "Statement of Purpose", requirement: "不超过 1000 字" },
  { id: "personal-history", kind: "PS", title: "Personal History Statement", requirement: "不超过 750 字" },
  { id: "career-short-answer", kind: "PS", title: "Short Answer · Career Goal", requirement: "不超过 250 字" },
  { id: "recommendation-1", kind: "推荐信", title: "推荐信 1 · 科研导师", requirement: "学术推荐人" },
  { id: "recommendation-2", kind: "推荐信", title: "推荐信 2 · 课程导师", requirement: "学术推荐人" },
  { id: "recommendation-3", kind: "推荐信", title: "推荐信 3 · 实习主管", requirement: "专业推荐人" },
];

const matched = [
  { name: "成绩单", source: "画像初始材料 · 本科成绩单-中文.pdf", detail: "已匹配 PDF · 2026-07-18 上传" },
  { name: "语言成绩", source: "画像信息 · TOEFL 105", detail: "达到官网要求 TOEFL 100" },
  { name: "在读证明", source: "画像初始材料 · 在读证明-英文.pdf", detail: "已匹配英文版" },
];

const officialRequirements = [
  { name: "CV / Resume", rule: "英文，建议 1–2 页", required: true, state: "需要确认" },
  { name: "Statement of Purpose", rule: "不超过 1000 字，说明技术背景、申请动机与职业目标", required: true, state: "需要生成" },
  { name: "推荐信", rule: "3 封，至少 2 封来自学术推荐人", required: true, state: "需要确认" },
  { name: "本科成绩单", rule: "完整成绩单，非英文文件需提供翻译件", required: true, state: "已匹配" },
  { name: "语言成绩", rule: "TOEFL 100 或 IELTS 7.5", required: true, state: "已匹配" },
  { name: "在读证明", rule: "英文版或附认证翻译", required: true, state: "已匹配" },
  { name: "护照信息页", rule: "清晰的 PDF 或图片扫描件", required: true, state: "缺少" },
  { name: "资金证明", rule: "录取后阶段提交", required: false, state: "稍后准备" },
];

const writingOptions: Record<WritingKind, { label: string; meta: string; fit: string }[]> = {
  CV: [
    { label: "通用英文 CV v3", meta: "已确认 · 2026-08-02", fit: "内容可复用，建议突出系统与 AI 项目" },
    { label: "CMU 项目 CV v1", meta: "历史项目版 · 2026-07-21", fit: "结构接近，但学校定制信息需要替换" },
  ],
  PS: [
    { label: "通用申请动机 PS v2", meta: "已确认 · 2026-07-26", fit: "可作为素材，不建议直接提交" },
    { label: "UCSD CS PS v1", meta: "历史项目版 · 2026-07-12", fit: "研究经历匹配，项目动机需要重写" },
  ],
  推荐信: [
    { label: "张老师推荐信素材包 v2", meta: "用户已确认 · 推荐人待确认", fit: "科研内容与当前项目相关" },
    { label: "实习主管推荐信素材包 v1", meta: "用户已确认 · 2026-06-30", fit: "工程能力匹配，学术能力证据较弱" },
  ],
};

function StatusPill({ tone, children }: { tone: "ready" | "work" | "missing"; children: React.ReactNode }) {
  const styles = {
    ready: "bg-emerald-100 text-emerald-800",
    work: "bg-amber-100 text-amber-800",
    missing: "bg-red-100 text-red-700",
  };
  return <span className={cn("inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-black", styles[tone])}>{children}</span>;
}

export default function PackagePreviewPage() {
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [confirmed, setConfirmed] = useState<Record<string, boolean>>({});
  const [savedAt, setSavedAt] = useState("");
  const [dialog, setDialog] = useState<MaterialSlot | null>(null);
  const [draftChoice, setDraftChoice] = useState("");

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(PREVIEW_STORAGE_KEY);
      if (!raw) return;
      const saved = JSON.parse(raw) as {
        selected?: Record<string, string>;
        confirmed?: Record<string, boolean>;
        savedAt?: string;
      };
      if (saved.selected) setSelected(saved.selected);
      if (saved.confirmed) setConfirmed(saved.confirmed);
      if (saved.savedAt) setSavedAt(saved.savedAt);
    } catch {
      window.localStorage.removeItem(PREVIEW_STORAGE_KEY);
    }
  }, []);

  const choose = (slotId: string, value: string) => {
    setSelected((current) => ({ ...current, [slotId]: value }));
    setConfirmed((current) => ({ ...current, [slotId]: false }));
  };
  const savePackage = () => {
    const nextSavedAt = new Date().toISOString();
    window.localStorage.setItem(PREVIEW_STORAGE_KEY, JSON.stringify({ selected, confirmed, savedAt: nextSavedAt }));
    setSavedAt(nextSavedAt);
  };
  const completed = matched.length + materialSlots.filter((slot) => confirmed[slot.id]).length;
  const total = matched.length + materialSlots.length + 1;

  return <div className="mx-auto max-w-7xl pb-16">
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
      <Link href="/shortlist" className="inline-flex items-center gap-2 text-sm font-bold text-ink/55 hover:text-moss"><ArrowLeft size={16} />返回选校清单</Link>
      <div className="flex flex-wrap items-center gap-2">{savedAt && <span className="text-xs font-bold text-ink/40">上次保存：{new Date(savedAt).toLocaleString("zh-CN")}</span>}<span className="rounded-full border border-violet-200 bg-violet-50 px-3 py-1.5 text-xs font-black text-violet-700">交互预览 · 本机保存</span><Button size="sm" onClick={savePackage}><Save size={14} />保存申请包</Button></div>
    </div>

    <section className="overflow-hidden rounded-[28px] bg-ink text-white shadow-soft">
      <div className="grid gap-7 p-6 md:grid-cols-[1fr_270px] md:p-8">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.2em] text-emerald-300">Georgia Institute of Technology · MSCS</p>
          <h1 className="mt-3 text-3xl font-black tracking-tight">项目申请包</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-white/60">系统已用官网要求匹配你的画像和历史材料。你只需要处理需要修改和缺少的项目。</p>
          <div className="mt-6 flex flex-wrap gap-2"><span className="rounded-full bg-white/10 px-3 py-1.5 text-xs font-bold">主申 · 匹配分 89</span><span className="rounded-full bg-white/10 px-3 py-1.5 text-xs font-bold">2027 Fall</span><span className="rounded-full bg-white/10 px-3 py-1.5 text-xs font-bold">截止 2026-12-15</span></div>
        </div>
        <div className="rounded-2xl bg-white/10 p-5">
          <div className="flex items-end justify-between"><div><p className="text-xs font-bold text-white/50">申请包完成度</p><strong className="mt-1 block text-4xl">{completed}/{total}</strong></div><span className="text-sm font-bold text-emerald-300">{Math.round(completed / total * 100)}%</span></div>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/10"><div className="h-full rounded-full bg-emerald-300 transition-all" style={{ width: `${completed / total * 100}%` }} /></div>
          <p className="mt-3 text-xs leading-5 text-white/50">全部必需材料确认后，才能进入申请看板。</p>
        </div>
      </div>
    </section>

    <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_300px]">
      <main className="space-y-6">
        <Card className="border-blue-100">
          <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="eyebrow">Official requirements</p><h2 className="mt-2 text-xl font-black">官网材料清单</h2><p className="mt-1 text-sm text-ink/50">先看项目要求，再处理匹配、生成和补充。以下要求均可追溯到官网原文。</p></div><Button size="sm" variant="secondary"><Link2 size={14} />查看全部官网证据</Button></div>
          <div className="mt-5 overflow-x-auto"><table className="w-full min-w-[720px] text-left text-sm"><thead><tr className="border-b border-black/10 text-xs text-ink/45"><th className="pb-3">官网要求</th><th className="pb-3">具体要求</th><th className="pb-3">类型</th><th className="pb-3 text-right">当前状态</th></tr></thead><tbody>{officialRequirements.map((item) => <tr key={item.name} className="border-b border-black/5 last:border-0"><td className="py-3.5 pr-4 font-black">{item.name}</td><td className="py-3.5 pr-4 text-ink/55">{item.rule}</td><td className="py-3.5 pr-4 text-xs font-bold text-ink/45">{item.required ? "必需" : "后续阶段"}</td><td className="py-3.5 text-right"><span className={cn("rounded-full px-2.5 py-1 text-xs font-black", item.state === "已匹配" ? "bg-emerald-100 text-emerald-700" : item.state === "缺少" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-800")}>{item.state}</span></td></tr>)}</tbody></table></div>
          <p className="mt-4 text-xs text-ink/40">最近核验：2026-08-13 · 来源：Graduate Admissions、MSCS Program Requirements</p>
        </Card>

        <Card className="border-emerald-100">
          <div className="flex items-start justify-between gap-4"><div><p className="eyebrow">Auto-matched</p><h2 className="mt-2 text-xl font-black">已从画像自动匹配</h2><p className="mt-1 text-sm text-ink/50">这些材料已经找到对应资产，无需重复上传或登记。</p></div><StatusPill tone="ready"><CheckCircle2 size={13} />{matched.length} 项已匹配</StatusPill></div>
          <div className="mt-5 divide-y divide-black/5">{matched.map((item) => <div key={item.name} className="grid gap-3 py-4 first:pt-0 last:pb-0 sm:grid-cols-[150px_1fr_auto] sm:items-center"><div className="flex items-center gap-2 font-black"><span className="grid size-8 place-items-center rounded-xl bg-emerald-100 text-emerald-700"><Check size={15} /></span>{item.name}</div><div><p className="text-sm font-bold">{item.source}</p><p className="mt-1 text-xs text-ink/45">{item.detail}</p></div><Button size="sm" variant="ghost">查看</Button></div>)}</div>
        </Card>

        <section>
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3"><div><p className="eyebrow">Choose or create</p><h2 className="mt-2 text-2xl font-black">需要你确认的核心材料</h2><p className="mt-1 text-sm text-ink/50">官网要求被拆成独立材料槽位。每个槽位确认一个最终版本，文书和推荐信可以有多份。</p></div><StatusPill tone="work"><Clock3 size={13} />{materialSlots.filter((slot) => !confirmed[slot.id]).length} 项待确认</StatusPill></div>
          {(["CV", "PS", "推荐信"] as WritingKind[]).map((group) => { const slots = materialSlots.filter((slot) => slot.kind === group); const done = slots.filter((slot) => confirmed[slot.id]).length; return <div key={group} className="mb-5 rounded-[24px] border border-black/5 bg-white/45 p-4 last:mb-0"><div className="mb-3 flex items-center justify-between"><div className="flex items-center gap-2"><span className={cn("grid size-9 place-items-center rounded-xl", group === "PS" ? "bg-violet-100 text-violet-700" : group === "推荐信" ? "bg-blue-100 text-blue-700" : "bg-emerald-100 text-emerald-700")}>{group === "推荐信" ? <UserRound size={17} /> : <FileText size={17} />}</span><div><h3 className="font-black">{group === "PS" ? "项目文书" : group}</h3><p className="text-xs text-ink/40">{done}/{slots.length} 已确认</p></div></div>{slots.length > 1 && <span className="rounded-full bg-white px-2.5 py-1 text-xs font-bold text-ink/50">{slots.length} 个独立槽位</span>}</div><div className="space-y-3">{slots.map((slot) => <Card key={slot.id} className={cn("grid gap-4 p-4 shadow-none md:grid-cols-[1fr_auto] md:items-center", confirmed[slot.id] && "border-emerald-200 bg-emerald-50/35")}><div><div className="flex flex-wrap items-center gap-2"><h4 className="text-sm font-black">{slot.title}</h4>{confirmed[slot.id] ? <StatusPill tone="ready"><Check size={12} />已确认</StatusPill> : selected[slot.id] ? <StatusPill tone="work">待确认</StatusPill> : <span className="rounded-full bg-stone-100 px-2 py-0.5 text-[11px] font-bold text-stone-600">尚未选择</span>}</div><p className="mt-1 text-xs text-ink/45">{slot.requirement}</p>{selected[slot.id] && <p className="mt-2 text-xs font-bold text-moss">当前版本：{selected[slot.id]}</p>}</div><div className="flex flex-wrap gap-2"><Button size="sm" variant="secondary" onClick={() => { setDraftChoice(selected[slot.id] ?? ""); setDialog(slot); }}><FolderOpen size={14} />历史版本</Button><Link href={`/assistant-preview?slot=${encodeURIComponent(slot.id)}`}><Button size="sm"><Bot size={14} />让 AI 助手生成</Button></Link>{selected[slot.id] && !confirmed[slot.id] && <Button size="sm" variant="ghost" onClick={() => setConfirmed((current) => ({ ...current, [slot.id]: true }))}><Check size={14} />确认使用</Button>}</div></Card>)}</div></div>; })}
        </section>

        <Card className="border-red-100">
          <div className="flex items-start justify-between gap-4"><div><p className="eyebrow">Missing</p><h2 className="mt-2 text-xl font-black">缺少的材料</h2><p className="mt-1 text-sm text-ink/50">画像和历史材料中没有找到对应文件。</p></div><StatusPill tone="missing"><CircleAlert size={13} />2 项缺少</StatusPill></div>
          <div className="mt-5 grid gap-3 md:grid-cols-2"><div className="rounded-2xl border border-dashed border-red-200 bg-red-50/40 p-4"><p className="font-black">护照信息页</p><p className="mt-1 text-xs leading-5 text-ink/50">官网要求清晰扫描件，当前初始材料中未找到。</p><Button className="mt-4" size="sm" variant="secondary"><Upload size={14} />上传材料</Button></div><div className="rounded-2xl border border-dashed border-red-200 bg-red-50/40 p-4"><p className="font-black">资金证明</p><p className="mt-1 text-xs leading-5 text-ink/50">录取后阶段需要，当前可以稍后准备。</p><Button className="mt-4" size="sm" variant="secondary"><Plus size={14} />添加准备记录</Button></div></div>
        </Card>
      </main>

      <aside className="space-y-5 xl:sticky xl:top-8 xl:self-start">
        <Card><p className="eyebrow">Next action</p><h2 className="mt-2 text-lg font-black">下一步做什么</h2><ol className="mt-4 space-y-4">{[
          [confirmed.cv, "确认当前项目 CV"],
          [materialSlots.filter((slot) => slot.kind === "PS").every((slot) => confirmed[slot.id]), "确认 3 项项目文书"],
          [materialSlots.filter((slot) => slot.kind === "推荐信").every((slot) => confirmed[slot.id]), "确认 3 封推荐信"],
          [false, "补充 2 项缺少材料"],
        ].map(([done, label], index) => <li key={String(label)} className="flex gap-3"><span className={cn("grid size-7 shrink-0 place-items-center rounded-full text-xs font-black", done ? "bg-emerald-100 text-emerald-700" : "bg-paper text-ink/45")}>{done ? <Check size={13} /> : index + 1}</span><span className={cn("pt-1 text-sm font-bold", done && "text-ink/35 line-through")}>{label}</span></li>)}</ol></Card>
        <Card><Save className="text-moss" size={20} /><h3 className="mt-3 font-black">保存后继续处理</h3><p className="mt-2 text-xs leading-5 text-ink/50">保存历史版本选择、生成依据和确认状态。下次打开这个项目申请包时继续显示当前进度。</p><Button className="mt-4 w-full" variant="secondary" onClick={savePackage}><Save size={14} />保存当前进度</Button></Card>
        <Button className="h-12 w-full" disabled={completed < total}><Sparkles size={16} />进入申请看板 <ChevronRight size={16} /></Button>
        {completed < total && <p className="text-center text-xs leading-5 text-ink/40">完成全部必需材料后开放</p>}
      </aside>
    </div>

    {dialog && <div className="fixed inset-0 z-[70] grid place-items-center bg-ink/55 p-4" role="dialog" aria-modal="true">
      <div className="max-h-[88vh] w-full max-w-2xl overflow-y-auto rounded-[24px] bg-white shadow-2xl">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-black/5 bg-white/95 px-5 py-4 backdrop-blur"><div><p className="text-xs font-black uppercase tracking-[0.16em] text-moss">Resource library</p><h2 className="mt-1 text-lg font-black">为“{dialog.title}”选择历史版本</h2></div><button type="button" onClick={() => setDialog(null)} className="grid size-9 place-items-center rounded-full bg-paper text-ink/50" aria-label="关闭"><X size={17} /></button></div>
        <div className="p-5"><p className="text-sm leading-6 text-ink/55">每个官网材料槽位只确认一个最终版本。可以选择历史版本，也可以关闭后进入 AI 助手生成新版本。</p><div className="mt-5 space-y-3">{writingOptions[dialog.kind].map((option) => <button type="button" key={option.label} onClick={() => setDraftChoice(option.label)} className={cn("w-full rounded-2xl border p-4 text-left transition", draftChoice === option.label ? "border-moss bg-mint/45 ring-2 ring-mint" : "border-black/5 hover:border-moss/30")}><div className="flex items-start gap-3"><span className={cn("mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border", draftChoice === option.label ? "border-moss bg-moss text-white" : "border-black/20")}>{draftChoice === option.label && <Check size={12} />}</span><span><span className="block text-sm font-black">{option.label}</span><span className="mt-1 block text-xs text-ink/45">{option.meta}</span><span className="mt-3 block rounded-xl bg-paper px-3 py-2 text-xs leading-5 text-ink/55">系统判断：{option.fit}</span></span></div></button>)}</div><div className="mt-6 flex justify-end gap-2"><Button variant="ghost" onClick={() => setDialog(null)}>取消</Button><Button disabled={!draftChoice} onClick={() => { choose(dialog.id, draftChoice); setDialog(null); }}><Check size={15} />使用所选版本</Button></div></div>
      </div>
    </div>}
  </div>;
}
