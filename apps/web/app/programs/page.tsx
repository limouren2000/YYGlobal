"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ExternalLink, Plus, RefreshCw, Search, Trash2 } from "lucide-react";
import { useState } from "react";
import { PageHeader } from "@/components/page-header";
import { ProcessGuide } from "@/components/process-guide";
import { useRecommendations } from "@/components/recommendation-provider";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function ProgramsPage() {
  const client = useQueryClient();
  const {
    profile, profileReady, input, setInput, queryText, items, latestBatchIds,
    selected, setSelected, recommendationNotice, isPending, error,
    profileChoiceOpen, requestBatch, restartForChangedProfile,
    appendForChangedProfile, dismissProfileChoice,
  } = useRecommendations();
  const [shortlistNotice, setShortlistNotice] = useState("");
  const shortlists = useQuery({ queryKey: ["shortlists"], queryFn: api.shortlists });
  const shortlist = shortlists.data?.[0];
  const joined = new Set(shortlist?.items.map((item) => item.program.id) ?? []);
  const latest = new Set(latestBatchIds);
  const add = useMutation({
    mutationFn: (ids: string[]) => api.addShortlistItems(ids),
    onSuccess: () => {
      setSelected([]);
      setShortlistNotice("已加入选校清单。推荐任务仍在继续。");
      client.invalidateQueries({ queryKey: ["shortlists"] });
      client.invalidateQueries({ queryKey: ["application-packages"] });
    },
    onError: (error) => setShortlistNotice(error instanceof Error ? error.message : "加入失败"),
  });
  const remove = useMutation({
    mutationFn: ({ shortlistId, programId }: { shortlistId: string; programId: string }) => api.removeShortlistItem(shortlistId, programId),
    onSuccess: () => {
      setShortlistNotice("已从选校清单移除。推荐任务仍在继续。");
      client.invalidateQueries({ queryKey: ["shortlists"] });
      client.invalidateQueries({ queryKey: ["application-packages"] });
    },
    onError: (error) => setShortlistNotice(error instanceof Error ? error.message : "移除失败"),
  });

  const toggle = (id: string) => setSelected((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);

  return <div className="mx-auto max-w-7xl">
    <PageHeader
      eyebrow="Profile-grounded recommendations"
      title="项目推荐"
      description="系统读取完整画像与已确认经历，每次新增 5 个项目，并自动读取官网要求和原文证据。"
      actions={<Button onClick={() => add.mutate(selected)} disabled={!selected.length || add.isPending}>加入选校清单（{selected.length}）</Button>}
    />
    <ProcessGuide current={1} completed={[0]} />
    {shortlistNotice && <div className="mb-5 rounded-xl bg-mint/70 px-4 py-3 text-sm text-moss">{shortlistNotice}</div>}
    {recommendationNotice && <div className="mb-5 rounded-xl bg-sky-50 px-4 py-3 text-sm text-sky-800">{recommendationNotice}</div>}
    <Card className="mb-6">
      <form onSubmit={(event) => { event.preventDefault(); requestBatch(true, input.trim()); }} className="flex flex-col gap-2 md:flex-row">
        <div className="relative flex-1"><Search className="absolute left-3 top-3 text-ink/35" size={17} /><input className="field pl-10" value={input} onChange={(event) => setInput(event.target.value)} placeholder="按完整画像推荐，或搜索学校、项目和专业方向" /></div>
        <Button type="submit" disabled={isPending}>开始新的检索</Button>
        <Button type="button" variant="secondary" onClick={() => requestBatch(false)} disabled={isPending || !items.length}><Plus size={15} />再推荐 5 个</Button>
      </form>
      <p className="mt-3 text-xs text-ink/45">{queryText ? `搜索方向：${queryText}` : `画像方向：${profile?.target_fields.join("、") || "请先完善画像"}`} · 新推荐添加在顶部，已有结果不会消失</p>
    </Card>
    {!queryText && !profileReady && <Card className="mb-6 border-amber-200 bg-amber-50 text-center"><h2 className="text-lg font-black text-amber-900">请先完成申请画像</h2><p className="mt-2 text-sm text-amber-800">确认目标国家、专业、成绩、偏好和真实经历后，系统会自动开始推荐。</p><a className="mt-4 inline-flex text-sm font-black text-amber-900 underline" href="/profile">前往填写画像</a></Card>}
    {isPending && <Card className="mb-6 py-12 text-center"><RefreshCw className="mx-auto animate-spin text-moss" /><p className="mt-4 font-black">正在检索并核验新一批 5 个项目官网…</p><p className="mt-2 text-sm text-ink/45">切换到其他页面不会中断推荐，完成后会保留结果。</p></Card>}
    {error && <Card className="mb-6 border-red-200 bg-red-50 text-sm text-red-800">{error.message}</Card>}
    <div className="grid gap-4 xl:grid-cols-2">
      {items.map(({ program, score, reasons }) => {
        const active = selected.includes(program.id);
        const isJoined = joined.has(program.id);
        const isLatest = latest.has(program.id);
        const requirement = program.requirement;
        return <Card key={program.id} className={cn("relative transition", (active || isJoined) && "border-moss/40 ring-2 ring-moss/10", isLatest && "border-sky-300")}>
          {isLatest && <span className="absolute right-4 top-4 rounded-full bg-sky-100 px-2.5 py-1 text-[11px] font-black text-sky-700">新推荐</span>}
          <div className="flex items-start gap-4 pr-16">
            {!isJoined && <button type="button" onClick={() => toggle(program.id)} className={cn("mt-1 grid size-6 shrink-0 place-items-center rounded-lg border transition", active ? "border-moss bg-moss text-white" : "border-black/15 bg-white")} aria-label={active ? "取消选择" : "选择项目"}>{active && <Check size={14} />}</button>}
            <div className="min-w-0 flex-1"><p className="eyebrow">{program.country} · {program.city}</p><h2 className="mt-2 text-lg font-black leading-6">{program.university}</h2><p className="mt-1 text-sm text-ink/60">{program.name}</p><span className="mt-2 inline-flex rounded-full bg-sky-50 px-2.5 py-1 text-[11px] font-bold text-sky-700">{program.field} · {program.degree}</span></div>
            <div className="text-right"><strong className="text-2xl text-moss">{score.toFixed(0)}</strong><p className="text-[10px] font-bold text-ink/40">匹配分</p></div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">{reasons.slice(0, 5).map((reason) => <span key={reason} className="rounded-full bg-mint/60 px-2.5 py-1 text-xs text-moss">{reason}</span>)}</div>
          <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4">{[
            ["学费", program.tuition ? `${program.currency} ${program.tuition.toLocaleString()}` : "官网未列出"],
            ["截止", requirement?.deadline ?? "官网未列出"],
            ["GPA", requirement?.min_gpa ? `≥ ${requirement.min_gpa}` : "官网未列出"],
            ["语言", requirement?.language.TOEFL ? `TOEFL ${requirement.language.TOEFL}` : requirement?.language.IELTS ? `IELTS ${requirement.language.IELTS}` : "官网未列出"],
          ].map(([label, value]) => <div key={label} className="rounded-xl bg-paper/80 p-3"><p className="text-[11px] font-bold uppercase tracking-wider text-ink/40">{label}</p><p className="mt-1 text-sm font-bold">{value}</p></div>)}</div>
          {!!requirement?.materials.length && <div className="mt-4"><p className="label">申请材料</p><div className="mt-2 flex flex-wrap gap-2">{requirement.materials.map((item) => <span key={item} className="rounded-full bg-paper px-2.5 py-1 text-xs text-ink/65">{item}</span>)}</div></div>}
          {!!requirement?.prerequisites.length && <div className="mt-4"><p className="label">背景要求</p><p className="mt-1 text-sm leading-6 text-ink/60">{requirement.prerequisites.join("、")}</p></div>}
          {program.evidence.length > 0 && <details className="mt-4 rounded-xl border border-emerald-100 bg-emerald-50/60 p-3" open><summary className="cursor-pointer text-xs font-black text-emerald-800">官网原文证据（{program.evidence.length}）</summary><div className="mt-3 space-y-2">{program.evidence.slice(0, 8).map((item) => <blockquote key={item.id} className="border-l-2 border-emerald-300 pl-3 text-xs leading-5 text-ink/60"><span className="font-black text-emerald-800">{item.field}</span>：{item.quote}</blockquote>)}</div></details>}
          <div className="mt-5 flex items-center justify-between border-t border-black/5 pt-4"><a href={program.official_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-xs font-bold text-moss hover:underline">查看官方页面 <ExternalLink size={13} /></a>{isJoined && shortlist ? <Button variant="ghost" size="sm" onClick={() => remove.mutate({ shortlistId: shortlist.id, programId: program.id })} disabled={remove.isPending}><Trash2 size={13} />已加入 · 移除</Button> : <Button size="sm" variant="secondary" onClick={() => add.mutate([program.id])} disabled={add.isPending}>加入选校</Button>}</div>
        </Card>;
      })}
    </div>

    {profileChoiceOpen && <div className="fixed inset-0 z-50 grid place-items-center bg-ink/45 p-4" role="dialog" aria-modal="true" aria-labelledby="profile-change-title">
      <Card className="w-full max-w-xl border-white bg-white shadow-2xl">
        <p className="eyebrow">申请画像已更新</p>
        <h2 id="profile-change-title" className="mt-2 text-xl font-black">如何处理已有推荐结果？</h2>
        <p className="mt-3 text-sm leading-6 text-ink/60">画像变化可能影响匹配分和项目排序。请选择本次如何处理，系统不会自动清空你的结果。</p>
        <div className="mt-6 grid gap-3">
          <Button onClick={restartForChangedProfile} disabled={isPending}>清空结果，按新画像从第一批开始</Button>
          <Button variant="secondary" onClick={appendForChangedProfile} disabled={isPending}>保留现有结果，按新画像再追加 5 个</Button>
          <Button variant="ghost" onClick={dismissProfileChoice}>暂不处理，继续查看现有结果</Button>
        </div>
      </Card>
    </div>}
  </div>;
}
