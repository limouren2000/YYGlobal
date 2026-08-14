"use client";

import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Check, Clock3 } from "lucide-react";
import { useState } from "react";
import { PageHeader } from "@/components/page-header";
import { ProcessGuide } from "@/components/process-guide";
import { Status } from "@/components/status";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api, Application, Task } from "@/lib/api";

const columns = [
  { key: "todo", title: "待开始" },
  { key: "doing", title: "进行中" },
  { key: "done", title: "已完成" },
];

const applicationStatuses: { key: Application["status"]; label: string }[] = [
  { key: "planning", label: "规划中" }, { key: "materials", label: "准备材料" },
  { key: "ready", label: "待提交" }, { key: "submitted", label: "已提交" },
  { key: "interview", label: "面试" }, { key: "offer", label: "Offer" },
  { key: "rejected", label: "未录取" }, { key: "withdrawn", label: "已撤回" },
];

export default function ApplicationsPage() {
  const client = useQueryClient();
  const [programId, setProgramId] = useState("");
  const [notice, setNotice] = useState("");
  const [programs, tasks, applications, packages] = useQueries({ queries: [
    { queryKey: ["programs"], queryFn: () => api.programs() },
    { queryKey: ["tasks"], queryFn: api.tasks },
    { queryKey: ["applications"], queryFn: api.applications },
    { queryKey: ["application-packages"], queryFn: api.applicationPackages },
  ] });
  const timeline = useMutation({ mutationFn: api.createTimeline, onSuccess: () => { setNotice("已根据截止日期倒排 6 个申请里程碑。未核验截止日期仍会显示风险。 "); client.invalidateQueries({ queryKey: ["tasks"] }); }, onError: (error) => setNotice(error instanceof Error ? error.message : "生成失败") });
  const update = useMutation({ mutationFn: ({ id, status }: { id: string; status: string }) => api.updateTask(id, { status }), onSuccess: () => client.invalidateQueries({ queryKey: ["tasks"] }) });
  const addApplication = useMutation({ mutationFn: api.createApplication, onSuccess: () => { setNotice("项目已加入申请看板。"); client.invalidateQueries({ queryKey: ["applications"] }); }, onError: (error) => setNotice(error instanceof Error ? error.message : "添加失败") });
  const updateApplication = useMutation({ mutationFn: ({ id, status }: { id: string; status: Application["status"] }) => api.updateApplication(id, { status }), onSuccess: () => client.invalidateQueries({ queryKey: ["applications"] }) });
  const programMap = new Map(programs.data?.map((item) => [item.id, item]) ?? []);
  const allTasks = tasks.data ?? [];

  function nextStatus(task: Task) { return task.status === "todo" ? "doing" : task.status === "doing" ? "done" : "todo"; }
  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader eyebrow="Application execution" title="申请看板" description="以项目截止日期为锚点倒排研究、CV、PS、推荐信、成绩单和提交检查。任务状态是业务数据，不只存在于聊天消息里。" />
      <ProcessGuide current={4} completed={[0, 1, 2, 3]} />
      <Card className="mb-6 border-blue-100 bg-blue-50"><p className="font-black text-blue-950">什么时候可以进入这里？</p><p className="mt-2 text-sm leading-6 text-blue-900/70">在申请材料准备中为所有必需材料确定版本，并统一确认该项目的材料方案后，即可加入申请看板。</p></Card>
      {notice && <div className="mb-5 rounded-xl bg-mint/70 px-4 py-3 text-sm text-moss">{notice}</div>}
      <Card className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end"><label className="flex-1"><span className="label">选择已就绪的项目申请包</span><select className="field" value={programId} onChange={(event) => setProgramId(event.target.value)}><option value="">请选择项目</option>{packages.data?.filter((pack) => pack.ready).map((pack) => <option key={pack.program.id} value={pack.program.id}>{pack.program.university}｜{pack.program.requirement?.deadline ?? "截止日期待确认"}</option>)}</select>{!packages.data?.some((pack) => pack.ready) && <p className="mt-2 text-xs text-amber-700">当前没有材料全部就绪的项目，请先完成项目申请包。</p>}</label><Button variant="secondary" disabled={!programId || applications.data?.some((item) => item.program_id === programId)} onClick={() => addApplication.mutate(programId)}>加入申请看板</Button><Button disabled={!programId || timeline.isPending} onClick={() => timeline.mutate(programId)}><CalendarDays size={16} />确认生成 6 个任务</Button></Card>
      <Card className="mb-6"><p className="eyebrow">Application status</p><h2 className="mt-2 text-xl font-black">项目申请状态</h2><div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{applications.data?.map((application) => <div key={application.id} className="rounded-xl border border-black/5 bg-paper/70 p-3"><p className="text-sm font-bold">{programMap.get(application.program_id)?.university ?? application.program_id}</p><select className="field mt-3" value={application.status} onChange={(event) => updateApplication.mutate({ id: application.id, status: event.target.value as Application["status"] })}>{applicationStatuses.map((status) => <option key={status.key} value={status.key}>{status.label}</option>)}</select></div>)}{!applications.data?.length && <p className="text-sm text-ink/45">选择项目并加入后，可以手动推进申请状态。</p>}</div></Card>
      <div className="mb-5 grid gap-4 sm:grid-cols-3">{columns.map((column) => <Card key={column.key} className="flex items-center justify-between py-4"><span className="text-sm font-semibold text-ink/55">{column.title}</span><strong className="text-2xl">{allTasks.filter((item) => item.status === column.key).length}</strong></Card>)}</div>
      <div className="grid gap-5 xl:grid-cols-3">{columns.map((column) => <section key={column.key} className="rounded-2xl bg-black/[0.025] p-3"><div className="mb-3 flex items-center justify-between px-1"><h2 className="font-black">{column.title}</h2><span className="text-xs text-ink/35">{allTasks.filter((item) => item.status === column.key).length} 项</span></div><div className="space-y-3">{allTasks.filter((item) => item.status === column.key).map((task) => <Card key={task.id} className="p-4 shadow-none"><div className="flex items-start justify-between gap-3"><Status value={task.priority}>{task.priority === "high" ? "高优先" : "普通"}</Status><button className="grid size-7 place-items-center rounded-full bg-paper text-ink/40 transition hover:bg-mint hover:text-moss" title="推进任务状态" onClick={() => update.mutate({ id: task.id, status: nextStatus(task) })}>{task.status === "done" ? <Check size={14} /> : <Clock3 size={14} />}</button></div><h3 className="mt-3 text-sm font-bold leading-5">{task.title}</h3><p className="mt-2 text-xs text-ink/45">{programMap.get(task.program_id ?? "")?.name ?? task.category}</p><div className="mt-4 flex items-center gap-1.5 border-t border-black/5 pt-3 text-xs font-semibold text-ink/55"><CalendarDays size={13} />{task.due_date ?? "待设定"}</div></Card>)}{!allTasks.some((item) => item.status === column.key) && <div className="rounded-xl border border-dashed border-black/10 px-3 py-8 text-center text-xs text-ink/35">暂无任务</div>}</div></section>)}</div>
    </div>
  );
}
