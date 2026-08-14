"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Bot, Check, Download, GitCompareArrows, History, RotateCcw, Save } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api, MaterialDraft } from "@/lib/api";
import { cn } from "@/lib/utils";

type DiffRow = { type: "same" | "added" | "removed"; text: string };
const revisionLabel: Record<string, string> = { generated: "AI 首次生成", derived: "跨项目派生", ai_revision: "AI 修改", manual_edit: "手动编辑", restored: "恢复版本" };

function lineDiff(before: string, after: string): DiffRow[] {
  const left = before.split("\n");
  const right = after.split("\n");
  const cells = (left.length + 1) * (right.length + 1);
  if (cells > 120_000) {
    return before === after ? [{ type: "same", text: before }] : [
      { type: "removed", text: before },
      { type: "added", text: after },
    ];
  }
  const matrix = Array.from({ length: left.length + 1 }, () => new Uint16Array(right.length + 1));
  for (let i = left.length - 1; i >= 0; i -= 1) for (let j = right.length - 1; j >= 0; j -= 1) matrix[i][j] = left[i] === right[j] ? matrix[i + 1][j + 1] + 1 : Math.max(matrix[i + 1][j], matrix[i][j + 1]);
  const result: DiffRow[] = [];
  let i = 0; let j = 0;
  while (i < left.length && j < right.length) {
    if (left[i] === right[j]) { result.push({ type: "same", text: left[i] }); i += 1; j += 1; }
    else if (matrix[i + 1][j] >= matrix[i][j + 1]) { result.push({ type: "removed", text: left[i] }); i += 1; }
    else { result.push({ type: "added", text: right[j] }); j += 1; }
  }
  while (i < left.length) { result.push({ type: "removed", text: left[i] }); i += 1; }
  while (j < right.length) { result.push({ type: "added", text: right[j] }); j += 1; }
  return result;
}

export default function DraftEditorPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const client = useQueryClient();
  const drafts = useQuery({ queryKey: ["material-drafts"], queryFn: () => api.materialDrafts() });
  const selected = drafts.data?.find((item) => item.id === params.id);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [notice, setNotice] = useState("");
  const [mode, setMode] = useState<"edit" | "diff">("edit");
  const [compareId, setCompareId] = useState("");
  useEffect(() => { if (selected) { setTitle(selected.title); setContent(selected.content); setCompareId(selected.parent_id || selected.derived_from_id || ""); } }, [selected]);
  const history = useMemo(() => {
    if (!selected) return [];
    const rootId = selected.root_id || selected.id;
    return (drafts.data ?? []).filter((item) => (item.root_id || item.id) === rootId).sort((a, b) => b.version_number - a.version_number);
  }, [drafts.data, selected]);
  const compareCandidates = useMemo(() => {
    const rows = [...history];
    if (selected?.derived_from_id) {
      const source = drafts.data?.find((item) => item.id === selected.derived_from_id);
      if (source && !rows.some((item) => item.id === source.id)) rows.push(source);
    }
    return rows.filter((item) => item.id !== selected?.id);
  }, [drafts.data, history, selected]);
  const compareDraft = compareCandidates.find((item) => item.id === compareId);
  const diffRows = useMemo(() => lineDiff(compareDraft?.content ?? "", selected?.content ?? ""), [compareDraft?.content, selected?.content]);
  const dirty = Boolean(selected && (title.trim() !== selected.title || content !== selected.content));
  const latest = history[0];

  function cacheResult(result: MaterialDraft) {
    client.setQueryData<MaterialDraft[]>(["material-drafts"], (rows = []) => rows.some((item) => item.id === result.id) ? rows.map((item) => item.id === result.id ? result : item) : [result, ...rows]);
    client.invalidateQueries({ queryKey: ["writing-conversations"] });
    client.invalidateQueries({ queryKey: ["application-packages"] });
    if (result.id !== params.id) router.replace(`/library/drafts/${result.id}`);
  }
  const save = useMutation({
    mutationFn: (status: "draft" | "reviewed") => {
      if (!selected) throw new Error("文稿不存在");
      return api.updateMaterialDraft(selected.id, { ...(dirty ? { title: title.trim(), content } : {}), status });
    },
    onSuccess: (result) => { cacheResult(result); setNotice(result.status === "reviewed" ? "文稿已保存并标记为已确认。" : `修改已保存为 v${result.version_number}，旧版本仍可回看。`); },
    onError: (error) => setNotice(error instanceof Error ? error.message : "保存失败"),
  });
  const restore = useMutation({
    mutationFn: () => { if (!selected) throw new Error("文稿不存在"); return api.restoreMaterialDraft(selected.id); },
    onSuccess: (result) => { cacheResult(result); setNotice(`已基于 v${selected?.version_number} 创建恢复版本 v${result.version_number}。`); },
    onError: (error) => setNotice(error instanceof Error ? error.message : "恢复失败"),
  });
  const conversationId = typeof selected?.model_info.conversation_id === "string" ? selected.model_info.conversation_id : "";

  if (!drafts.isLoading && !selected) return <div className="mx-auto max-w-3xl py-20 text-center"><h1 className="text-xl font-black">文稿不存在</h1><Link href="/library"><Button className="mt-4">返回材料资源库</Button></Link></div>;
  return <div className="mx-auto max-w-7xl">
    <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><Link href="/library" className="inline-flex items-center gap-1 text-xs font-black text-ink/45"><ArrowLeft size={13} />返回材料资源库</Link><h1 className="mt-3 text-2xl font-black">编辑文稿</h1><p className="mt-1 text-sm text-ink/45">AI 修改和手动编辑会进入同一条版本链，每一版都可以比较和恢复。</p></div>{conversationId && selected && <Link href={`/assistant?conversation=${conversationId}&program=${selected.program_id ?? ""}&slot=${encodeURIComponent(selected.slot_key)}`}><Button variant="secondary"><Bot size={15} />继续让 AI 修改</Button></Link>}</div>
    {notice && <div className="mb-5 rounded-xl bg-mint/70 px-4 py-3 text-sm font-bold text-moss">{notice}</div>}
    <div className="grid gap-6 xl:grid-cols-[270px_1fr]">
      <Card className="h-fit xl:sticky xl:top-6"><div className="flex items-center gap-2"><History size={16} /><h2 className="font-black">版本历史</h2></div><p className="mt-1 text-xs text-ink/40">当前链共 {history.length} 个版本。</p>{selected?.derived_from_id && <p className="mt-3 rounded-lg bg-violet-50 px-3 py-2 text-[10px] font-bold text-violet-700">这条文稿链基于其他项目版本创建。</p>}<div className="mt-4 space-y-2">{history.map((item) => <Link key={item.id} href={`/library/drafts/${item.id}`} className={cn("block rounded-xl border p-3", item.id === selected?.id ? "border-moss bg-mint/50" : "border-black/5 hover:bg-paper")}><div className="flex items-center justify-between"><span className="text-xs font-black">v{item.version_number}</span>{item.status === "reviewed" && <Check size={13} className="text-emerald-600" />}</div><p className="mt-1 text-[10px] font-bold text-moss">{revisionLabel[item.revision_type] ?? item.revision_type}</p><p className="mt-1 line-clamp-2 text-[10px] text-ink/45">{item.change_summary}</p><p className="mt-1 text-[9px] text-ink/30">{new Date(item.updated_at).toLocaleString("zh-CN")}</p></Link>)}</div></Card>
      <Card className="min-h-[760px] p-0"><div className="flex flex-col gap-3 border-b border-black/5 p-5"><div className="flex flex-col gap-3 lg:flex-row lg:items-end"><label className="min-w-0 flex-1"><span className="label">文稿标题</span><input className="field w-full" value={title} onChange={(event) => setTitle(event.target.value)} disabled={mode === "diff"} /></label><div className="flex flex-wrap gap-2">{selected && <><a href={api.materialDraftExportUrl(selected.id, "docx")} download><Button variant="secondary"><Download size={14} />DOCX</Button></a><a href={api.materialDraftExportUrl(selected.id, "pdf")} download><Button variant="secondary"><Download size={14} />PDF</Button></a></>}<Button variant="secondary" onClick={() => setMode((value) => value === "edit" ? "diff" : "edit")} disabled={!compareCandidates.length}><GitCompareArrows size={14} />{mode === "diff" ? "返回编辑" : "查看 Diff"}</Button>{selected && latest && selected.id !== latest.id && <Button variant="secondary" onClick={() => restore.mutate()} disabled={restore.isPending}><RotateCcw size={14} />恢复为新版本</Button>}<Button variant="secondary" disabled={!dirty || save.isPending || mode === "diff"} onClick={() => save.mutate("draft")}><Save size={14} />保存修改</Button><Button disabled={(!dirty && selected?.status === "reviewed") || save.isPending || mode === "diff"} onClick={() => save.mutate("reviewed")}><Check size={14} />保存并确认</Button></div></div>{mode === "diff" && <div className="flex flex-wrap items-center gap-2 rounded-xl bg-paper/70 p-3"><span className="text-xs font-black">比较版本</span><select className="field min-w-48" value={compareId} onChange={(event) => setCompareId(event.target.value)}>{compareCandidates.map((item) => <option key={item.id} value={item.id}>{item.id === selected?.derived_from_id ? "来源文稿" : `v${item.version_number}`} · {revisionLabel[item.revision_type] ?? item.revision_type}</option>)}</select><span className="text-xs text-ink/40">→ 当前 v{selected?.version_number}</span></div>}</div>
        <div className="p-5">{mode === "edit" ? <><div className="mb-3 flex items-center justify-between text-xs text-ink/40"><span>{selected ? `${selected.kind.toUpperCase()} · v${selected.version_number} · ${revisionLabel[selected.revision_type] ?? selected.revision_type}` : "正在读取文稿…"}</span><span>{dirty ? "有未保存修改" : selected?.status === "reviewed" ? "已确认" : "草稿"}</span></div><textarea aria-label="文稿正文编辑器" className="min-h-[620px] w-full resize-y rounded-2xl border border-black/10 bg-white p-5 font-mono text-sm leading-7 outline-none focus:border-moss" value={content} onChange={(event) => setContent(event.target.value)} /></> : <div><div className="mb-4 flex items-center gap-4 text-xs"><span className="rounded-full bg-red-100 px-2 py-1 font-bold text-red-700">− 删除</span><span className="rounded-full bg-emerald-100 px-2 py-1 font-bold text-emerald-700">+ 新增</span><span className="text-ink/35">未标色内容保持不变</span></div>{compareDraft ? <div className="max-h-[650px] overflow-y-auto rounded-2xl border border-black/5 bg-white p-4 font-mono text-sm leading-6">{diffRows.map((row, index) => <div key={`${index}:${row.type}`} className={cn("min-h-6 whitespace-pre-wrap px-2", row.type === "added" && "bg-emerald-50 text-emerald-900", row.type === "removed" && "bg-red-50 text-red-800 line-through", row.type === "same" && "text-ink/60")}><span className="mr-2 inline-block w-3 select-none text-ink/25">{row.type === "added" ? "+" : row.type === "removed" ? "−" : ""}</span>{row.text || " "}</div>)}</div> : <div className="rounded-xl bg-amber-50 p-4 text-sm text-amber-800">请选择一个用于比较的版本。</div>}</div>}</div>
      </Card>
    </div>
  </div>;
}
