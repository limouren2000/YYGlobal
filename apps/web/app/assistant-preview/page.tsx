"use client";

import { ArrowLeft, Bot, Check, ChevronDown, FileText, History, MessageSquarePlus, PanelRight, Send, Sparkles, UserRound } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const PACKAGE_KEY = "yyglobal-package-preview-georgia-tech";

const slotMeta: Record<string, { title: string; kind: string; requirement: string; prompt: string }> = {
  cv: { title: "CV / Resume", kind: "CV", requirement: "英文，建议 1–2 页", prompt: "重点突出 RAG 项目和后端工程能力，控制在一页。" },
  sop: { title: "Statement of Purpose", kind: "项目文书", requirement: "不超过 1000 字", prompt: "重点写科研动机、技术成长和 Georgia Tech 的项目匹配。" },
  "personal-history": { title: "Personal History Statement", kind: "项目文书", requirement: "不超过 750 字", prompt: "从个人成长和教育经历出发，语气自然，不要重复 SOP。" },
  "career-short-answer": { title: "Short Answer · Career Goal", kind: "项目文书", requirement: "不超过 250 字", prompt: "聚焦毕业后 3–5 年的 AI 工程职业目标。" },
  "recommendation-1": { title: "推荐信 1 · 科研导师", kind: "推荐信", requirement: "学术推荐人", prompt: "以科研导师视角突出研究主动性、技术深度和协作能力。" },
  "recommendation-2": { title: "推荐信 2 · 课程导师", kind: "推荐信", requirement: "学术推荐人", prompt: "以课程导师视角突出学习能力、课堂表现和项目成果。" },
  "recommendation-3": { title: "推荐信 3 · 实习主管", kind: "推荐信", requirement: "专业推荐人", prompt: "以实习主管视角突出工程能力、责任心和团队协作。" },
};

const conversations = [
  { title: "初版生成", time: "刚刚", active: true },
  { title: "加强科研动机", time: "昨天", active: false },
  { title: "压缩到官网字数", time: "8 月 11 日", active: false },
];

const resources = [
  ["完整申请画像", "画像"], ["多模态检索科研经历", "已确认经历"],
  ["AI 平台开发实习", "已确认经历"], ["Grounded RAG 项目", "已确认经历"],
  ["通用申请动机 PS v2", "历史文稿"], ["Georgia Tech 官网要求", "官网证据"],
];

export default function AssistantPreviewPage() {
  const [slotId, setSlotId] = useState("sop");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<{ role: "assistant" | "user"; text: string }[]>([]);
  const [version, setVersion] = useState(1);
  const [saved, setSaved] = useState(false);
  const meta = slotMeta[slotId] ?? slotMeta.sop;

  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get("slot") ?? "sop";
    const next = slotMeta[requested] ? requested : "sop";
    setSlotId(next);
    setMessages([
      { role: "assistant", text: `我正在协助你完成 Georgia Tech MSCS 的“${slotMeta[next].title}”。官网要求：${slotMeta[next].requirement}。我已经读取了官网要求、完整画像、确认经历和历史文稿。` },
      { role: "assistant", text: "我建议先生成一个结构清晰的初版，再通过对话逐轮调整。你希望这一版重点突出什么？" },
    ]);
  }, []);

  const send = () => {
    const text = input.trim();
    if (!text) return;
    setMessages((current) => [...current, { role: "user", text }, { role: "assistant", text: `收到。我会保留事实边界，并按“${text}”调整内容。已生成候选版本 v${version + 1}，你可以继续提出修改，或在右侧保存为正式版本。` }]);
    setVersion((current) => current + 1);
    setInput("");
  };

  const useForPackage = () => {
    let current: { selected?: Record<string, string>; confirmed?: Record<string, boolean>; savedAt?: string } = {};
    try { current = JSON.parse(window.localStorage.getItem(PACKAGE_KEY) ?? "{}"); } catch { current = {}; }
    const savedAt = new Date().toISOString();
    window.localStorage.setItem(PACKAGE_KEY, JSON.stringify({
      ...current,
      selected: { ...(current.selected ?? {}), [slotId]: `${meta.title} · Georgia Tech 项目版 v${version}` },
      confirmed: { ...(current.confirmed ?? {}), [slotId]: true },
      savedAt,
    }));
    setSaved(true);
  };

  return <div className="fixed inset-0 z-40 flex bg-[#f7f5ef] lg:left-64">
    <aside className="hidden w-64 shrink-0 flex-col border-r border-black/5 bg-white/80 md:flex">
      <div className="border-b border-black/5 p-4"><Link href="/package-preview" className="inline-flex items-center gap-2 text-xs font-black text-ink/55"><ArrowLeft size={14} />返回项目申请包</Link><Button className="mt-4 w-full" variant="secondary"><MessageSquarePlus size={15} />新建对话</Button></div>
      <div className="px-4 pt-4"><p className="text-[10px] font-black uppercase tracking-[0.16em] text-ink/35">Georgia Tech · MSCS</p><h1 className="mt-2 text-sm font-black">{meta.title}</h1></div>
      <nav className="mt-4 space-y-1 px-3">{conversations.map((item) => <button type="button" key={item.title} className={cn("w-full rounded-xl px-3 py-2.5 text-left", item.active ? "bg-ink text-white" : "hover:bg-paper")}><span className="block text-xs font-black">{item.title}</span><span className={cn("mt-1 block text-[10px]", item.active ? "text-white/45" : "text-ink/35")}>{item.time}</span></button>)}</nav>
      <div className="mt-auto border-t border-black/5 p-4 text-xs leading-5 text-ink/45"><History className="mb-2" size={16} />所有对话和生成版本都会保留，可以随时回来继续。</div>
    </aside>

    <main className="flex min-w-0 flex-1 flex-col">
      <header className="flex h-16 items-center justify-between border-b border-black/5 bg-white/75 px-4 backdrop-blur sm:px-6"><div className="flex items-center gap-3"><span className="grid size-9 place-items-center rounded-xl bg-violet-100 text-violet-700"><Bot size={18} /></span><div><p className="text-sm font-black">YYGlobal 文书助手</p><p className="text-[11px] text-ink/40">{meta.title} · 对话自动保存</p></div></div><div className="flex items-center gap-2"><span className="hidden rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-bold text-emerald-700 sm:inline">已读取官网要求</span><Button size="sm" onClick={useForPackage}><Check size={14} />保存并用于申请包</Button></div></header>
      <div className="flex-1 overflow-y-auto"><div className="mx-auto max-w-3xl px-4 py-8 sm:px-7"><div className="mb-8 text-center"><span className="mx-auto grid size-12 place-items-center rounded-2xl bg-ink text-white"><Sparkles size={20} /></span><h2 className="mt-4 text-2xl font-black">开始完善 {meta.title}</h2><p className="mt-2 text-sm text-ink/45">你可以像使用 ChatGPT 一样持续对话，每次调整都会形成新版本。</p></div><div className="space-y-6">{messages.map((message, index) => <div key={`${message.role}-${index}`} className={cn("flex gap-3", message.role === "user" && "justify-end")}><span className={cn("grid size-8 shrink-0 place-items-center rounded-xl", message.role === "assistant" ? "bg-violet-100 text-violet-700" : "order-2 bg-ink text-white")}>{message.role === "assistant" ? <Bot size={15} /> : <UserRound size={15} />}</span><div className={cn("max-w-[82%] rounded-2xl px-4 py-3 text-sm leading-6", message.role === "assistant" ? "rounded-tl-md bg-white shadow-sm" : "rounded-tr-md bg-ink text-white")}>{message.text}</div></div>)}</div></div></div>
      <div className="border-t border-black/5 bg-white/80 px-4 py-4 backdrop-blur"><div className="mx-auto max-w-3xl"><div className="rounded-2xl border border-black/10 bg-white p-2 shadow-soft"><textarea className="min-h-20 w-full resize-none border-0 bg-transparent px-3 py-2 text-sm outline-none" value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); send(); } }} placeholder={meta.prompt} /><div className="flex items-center justify-between px-2 pb-1"><button type="button" className="text-xs font-bold text-ink/45">添加资源或文件 <ChevronDown className="ml-1 inline" size={13} /></button><button type="button" onClick={send} className="grid size-9 place-items-center rounded-xl bg-ink text-white" aria-label="发送"><Send size={16} /></button></div></div><p className="mt-2 text-center text-[10px] text-ink/35">AI 只引用已确认资料，最终内容需要你本人确认。</p></div></div>
    </main>

    <aside className="hidden w-72 shrink-0 overflow-y-auto border-l border-black/5 bg-white/70 p-4 xl:block"><div className="flex items-center gap-2"><PanelRight size={16} /><h2 className="text-sm font-black">当前任务上下文</h2></div><section className="mt-5 rounded-2xl bg-blue-50 p-4"><p className="text-xs font-black text-blue-900">官网要求</p><p className="mt-2 text-sm font-bold text-blue-950">{meta.title}</p><p className="mt-1 text-xs leading-5 text-blue-900/55">{meta.requirement}</p><button className="mt-3 text-xs font-black text-blue-800">查看原文证据</button></section><section className="mt-5"><div className="flex items-center justify-between"><p className="text-xs font-black">参考资源</p><button className="text-xs font-bold text-moss">调整</button></div><div className="mt-3 space-y-2">{resources.map(([label, type]) => <div key={label} className="rounded-xl border border-black/5 bg-white p-3"><p className="text-xs font-black">{label}</p><p className="mt-1 text-[10px] text-ink/40">{type}</p></div>)}</div></section><section className="mt-5"><p className="text-xs font-black">生成版本</p><div className="mt-3 rounded-xl border border-emerald-100 bg-emerald-50 p-3"><div className="flex items-center justify-between"><p className="text-xs font-black">项目版 v{version}</p><span className="text-[10px] font-bold text-emerald-700">当前</span></div><p className="mt-1 text-[10px] text-ink/40">由当前对话生成</p></div><Button className="mt-3 w-full" variant="secondary"><FileText size={14} />打开完整文稿</Button></section>{saved && <div className="mt-5 rounded-xl bg-emerald-100 p-3 text-xs font-black text-emerald-800">已保存并确认用于当前申请包。</div>}</aside>
  </div>;
}
