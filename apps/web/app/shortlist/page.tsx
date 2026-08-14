"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, FolderKanban, Trash2 } from "lucide-react";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { ProcessGuide } from "@/components/process-guide";
import { Status } from "@/components/status";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";

const tierLabels = { reach: "冲刺", target: "主申", safer: "相对稳健" };

export default function ShortlistPage() {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["shortlists"], queryFn: api.shortlists });
  const packages = useQuery({ queryKey: ["application-packages"], queryFn: api.applicationPackages });
  const refresh = useMutation({ mutationFn: api.refreshApplicationPackage, onSuccess: () => client.invalidateQueries({ queryKey: ["application-packages"] }) });
  const remove = useMutation({ mutationFn: ({ shortlistId, programId }: { shortlistId: string; programId: string }) => api.removeShortlistItem(shortlistId, programId), onSuccess: () => { client.invalidateQueries({ queryKey: ["shortlists"] }); client.invalidateQueries({ queryKey: ["application-packages"] }); } });
  const shortlist = query.data?.[0];
  return <div className="mx-auto max-w-6xl">
    <PageHeader eyebrow="Decision support" title="选校清单" description="决定最终申请哪些项目；可以返回推荐页继续添加，也可以在这里移除。" actions={<Link href="/programs"><Button variant="secondary">继续添加项目</Button></Link>} />
    <ProcessGuide current={2} completed={[0, 1]} />
    {!query.isLoading && !shortlist && <Card className="py-16 text-center"><h2 className="text-xl font-black">还没有选校清单</h2><p className="mt-2 text-sm text-ink/50">先在项目探索中选择多个项目，再生成分层方案。</p><Link href="/programs"><Button className="mt-5">前往项目探索</Button></Link></Card>}
    {shortlist && <><Card className="mb-5 bg-ink text-white"><p className="text-xs font-bold uppercase tracking-[0.18em] text-white/50">Latest shortlist</p><h2 className="mt-2 text-2xl font-black">{shortlist.name}</h2><p className="mt-2 text-sm text-white/60">{shortlist.rationale}</p><div className="mt-5 flex gap-5 text-sm">{(["reach", "target", "safer"] as const).map((tier) => <span key={tier}><strong className="text-xl">{shortlist.items.filter((item) => item.tier === tier).length}</strong> <span className="text-white/50">{tierLabels[tier]}</span></span>)}</div></Card>
      <div className="space-y-4">{shortlist.items.map((item) => { const pack = packages.data?.find((value) => value.program.id === item.program.id); return <Card key={item.id} className="grid gap-4 md:grid-cols-[1fr_110px_1.1fr]">
        <div><div className="flex items-center gap-2"><Status value={item.tier}>{tierLabels[item.tier]}</Status><span className="text-xs font-bold text-ink/40">匹配分 {item.score.toFixed(0)}</span></div><h3 className="mt-3 text-lg font-black">{item.program.university}</h3><p className="mt-1 text-sm text-ink/55">{item.program.name}</p><a href={item.program.official_url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-xs font-bold text-moss">官网 <ExternalLink size={12} /></a></div>
        <div className="grid place-items-center"><div className="grid size-20 place-items-center rounded-full border-[7px] border-mint text-xl font-black text-moss">{item.score.toFixed(0)}</div></div>
        <div><p className="label">申请材料进度</p>{pack ? <><p className="text-sm font-bold">{pack.ready ? "材料已就绪" : "材料准备中"}</p><p className="mt-1 text-xs text-ink/45">{pack.checklist.filter((row) => row.status === "ready").length}/{pack.checklist.length} 项符合</p><div className="mt-3 flex flex-wrap gap-2"><Link href={`/materials?program=${item.program.id}`}><Button size="sm"><FolderKanban size={14} />准备申请材料</Button></Link><Button size="sm" variant="ghost" onClick={() => remove.mutate({ shortlistId: shortlist.id, programId: item.program.id })} disabled={remove.isPending}><Trash2 size={14} />移除项目</Button></div></> : <Button size="sm" variant="secondary" disabled={refresh.isPending} onClick={() => refresh.mutate(item.program.id)}>开始准备材料</Button>} {!!item.program.requirement?.materials.length && <><p className="label mt-4">官网申请材料</p><p className="mt-1 text-sm leading-6 text-ink/60">{item.program.requirement.materials.join("、")}</p></>} {item.program.evidence.length > 0 && <details className="mt-3"><summary className="cursor-pointer text-xs font-black text-emerald-800">查看官网原文证据（{item.program.evidence.length}）</summary><div className="mt-2 space-y-2">{item.program.evidence.slice(0, 6).map((evidence) => <blockquote key={evidence.id} className="border-l-2 border-emerald-300 pl-2 text-xs leading-5 text-ink/55">{evidence.quote}</blockquote>)}</div></details>}</div>
      </Card>; })}</div></>}
  </div>;
}
