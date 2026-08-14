"use client";

import { useQueries } from "@tanstack/react-query";
import { ArrowRight, Bot, BriefcaseBusiness, CheckCircle2, CircleDashed, FileText, GraduationCap } from "lucide-react";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";

const materialLabel: Record<string, string> = { cv: "CV", ps: "PS / Essay", recommendation: "推荐信" };

export default function DashboardPage() {
  const results = useQueries({ queries: [
    { queryKey: ["profile"], queryFn: api.profile },
    { queryKey: ["tasks"], queryFn: api.tasks },
    { queryKey: ["health"], queryFn: api.health },
    { queryKey: ["application-packages"], queryFn: api.applicationPackages },
    { queryKey: ["assistant-conversations"], queryFn: api.assistantConversations },
    { queryKey: ["documents"], queryFn: api.documents },
  ] });
  const profile = results[0].data;
  const tasks = results[1].data ?? [];
  const health = results[2].data;
  const packages = results[3].data ?? [];
  const conversations = results[4].data ?? [];
  const documents = results[5].data ?? [];
  const openTasks = tasks.filter((item) => item.status !== "done");
  const missingCount = packages.reduce((total, item) => total + item.checklist.filter((material) => material.status === "missing").length, 0);
  const confirmedCount = packages.filter((item) => item.plan_confirmed).length;

  return <div className="mx-auto max-w-7xl">
    <PageHeader eyebrow="Today workspace" title={`早上好${profile?.full_name ? `，${profile.full_name}` : ""}`} description="集中查看申请进度、待处理材料和最近对话，再进入对应工作区继续。" actions={<div className="flex items-center gap-2"><span className="hidden rounded-full border border-black/5 bg-white/70 px-3 py-1.5 text-xs text-ink/50 sm:inline">{health?.llm_mode === "dashscope" ? "阿里云百炼模式" : health?.llm_mode === "openai" ? "OpenAI 模式" : "本地可运行模式"}</span><Link href="/assistant"><Button><Bot size={15} />进入 AI 助手</Button></Link></div>} />

    <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {[
        { value: profile?.confirmed ? "画像已确认" : "画像待完善", label: "申请基础信息", icon: profile?.confirmed ? CheckCircle2 : CircleDashed, href: "/profile" },
        { value: `${packages.length} 个`, label: "已进入申请准备的项目", icon: GraduationCap, href: "/shortlist" },
        { value: `${confirmedCount}/${packages.length}`, label: "材料方案已确定", icon: FileText, href: "/materials" },
        { value: `${openTasks.length} 项`, label: "当前未完成任务", icon: BriefcaseBusiness, href: "/applications" },
      ].map(({ value, label, icon: Icon, href }) => <Link key={label} href={href} className="group"><Card className="flex h-full items-start justify-between transition group-hover:-translate-y-0.5 group-hover:border-moss/30 group-hover:shadow-md"><div><p className="text-2xl font-black">{value}</p><p className="mt-1 text-sm text-ink/50">{label}</p><p className="mt-3 flex items-center gap-1 text-xs font-bold text-moss opacity-0 transition group-hover:opacity-100">查看详情 <ArrowRight size={12} /></p></div><span className="rounded-xl bg-mint p-2 text-moss"><Icon size={18} /></span></Card></Link>)}
    </section>

    <section className="mt-6 grid gap-6 xl:grid-cols-[1.35fr_0.85fr]">
      <Card className="p-0">
        <div className="flex items-center justify-between border-b border-black/5 px-5 py-4"><div><p className="eyebrow">Application progress</p><h2 className="mt-1 text-xl font-black">申请项目进度</h2></div><Link href="/materials" className="text-xs font-black text-moss">查看全部</Link></div>
        <div className="divide-y divide-black/5">
          {packages.slice(0, 5).map((item) => {
            const ready = item.checklist.filter((material) => material.status === "ready").length;
            return <Link key={item.id} href={`/materials?program=${item.program.id}`} className="flex items-center gap-4 px-5 py-4 transition hover:bg-mint/30"><span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-paper font-black text-moss">{item.program.university.slice(0, 1)}</span><div className="min-w-0 flex-1"><p className="truncate text-sm font-black">{item.program.university}</p><p className="mt-1 truncate text-xs text-ink/45">{item.program.name}</p></div><div className="hidden text-right sm:block"><p className="text-xs font-black">{ready}/{item.checklist.length} 项材料就绪</p><p className="mt-1 text-[10px] text-ink/35">{item.plan_confirmed ? "方案已确定" : "正在准备"}</p></div><ArrowRight size={15} className="text-ink/25" /></Link>;
          })}
          {!packages.length && <div className="px-5 py-14 text-center"><p className="font-black">还没有申请项目</p><p className="mt-1 text-sm text-ink/45">先在项目推荐中选择项目并加入选校清单。</p><Link href="/programs"><Button className="mt-4" size="sm">开始项目推荐</Button></Link></div>}
        </div>
      </Card>

      <div className="space-y-6">
        <Card>
          <div className="flex items-center justify-between"><div><p className="eyebrow">Continue</p><h2 className="mt-1 text-xl font-black">继续处理</h2></div><Link href="/assistant"><span className="grid size-9 place-items-center rounded-xl bg-ink text-emerald-300"><Bot size={16} /></span></Link></div>
          <div className="mt-4 space-y-2">
            {conversations.slice(0, 4).map((item) => <Link key={item.id} href={item.scene === "material" ? `/assistant?conversation=${item.id}&program=${item.program_id}&slot=${encodeURIComponent(item.slot_key)}` : `/assistant?conversation=${item.id}`} className="block rounded-xl border border-black/5 bg-paper/60 p-3 transition hover:border-moss/25 hover:bg-mint/40"><div className="flex items-center justify-between gap-3"><span className="rounded-full bg-white px-2 py-1 text-[9px] font-black text-moss">{item.scene === "material" ? materialLabel[item.material_kind] ?? "材料写作" : "申请规划"}</span><span className="text-[9px] text-ink/30">{new Date(item.updated_at).toLocaleDateString("zh-CN")}</span></div><p className="mt-2 truncate text-xs font-black">{item.title}</p>{item.program_label && <p className="mt-1 truncate text-[10px] text-ink/40">{item.program_label}</p>}</Link>)}
            {!conversations.length && <p className="rounded-xl bg-paper/60 px-3 py-5 text-center text-sm text-ink/45">还没有 AI 对话记录。</p>}
          </div>
        </Card>
        <Card>
          <div className="flex items-center justify-between"><div><p className="eyebrow">Resources</p><h2 className="mt-1 text-xl font-black">材料与任务</h2></div><Link href="/library" className="text-xs font-black text-moss">管理文件</Link></div>
          <div className="mt-4 grid grid-cols-3 gap-2 text-center"><div className="rounded-xl bg-mint/60 p-3"><p className="text-xl font-black">{documents.length}</p><p className="mt-1 text-[10px] text-ink/45">资源文件</p></div><div className="rounded-xl bg-amber-50 p-3"><p className="text-xl font-black">{missingCount}</p><p className="mt-1 text-[10px] text-ink/45">待补材料</p></div><div className="rounded-xl bg-violet-50 p-3"><p className="text-xl font-black">{openTasks.length}</p><p className="mt-1 text-[10px] text-ink/45">待办任务</p></div></div>
          <div className="mt-4 space-y-3">{openTasks.slice(0, 3).map((task) => <div key={task.id} className="border-l-2 border-amber pl-3"><p className="truncate text-xs font-black">{task.title}</p><p className="mt-1 text-[10px] text-ink/40">{task.due_date ?? "待设定日期"}</p></div>)}{!openTasks.length && <p className="text-xs text-ink/40">当前没有待办任务。</p>}</div>
        </Card>
      </div>
    </section>
  </div>;
}
