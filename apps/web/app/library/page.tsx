"use client";

import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";
import { Bot, ChevronRight, Download, Eye, FileArchive, FileText, FileUp, Folder, Pencil, Search, Trash2 } from "lucide-react";
import Link from "next/link";
import { ChangeEvent, useMemo, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { MaterialPreviewDialog, PreviewTarget } from "@/components/material-preview-dialog";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api, MaterialDraft } from "@/lib/api";
import { cn } from "@/lib/utils";

const kindLabel: Record<string, string> = { cv: "CV", ps: "PS / Essay", recommendation: "推荐信", transcript: "成绩单", language: "语言成绩", portfolio: "作品集", writing_sample: "写作样本", other: "其他" };
const categories = [
  { value: "all", label: "全部文件", kinds: [] },
  { value: "academic", label: "学术与成绩", kinds: ["transcript", "language"] },
  { value: "core", label: "核心文书", kinds: ["cv", "ps", "recommendation"] },
  { value: "supplement", label: "补充材料", kinds: ["portfolio", "writing_sample", "other"] },
  { value: "ai", label: "AI 生成版本", kinds: [] },
];
const uploadKinds = Object.entries(kindLabel);

export default function LibraryPage() {
  const client = useQueryClient();
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [uploadKind, setUploadKind] = useState("other");
  const [notice, setNotice] = useState("");
  const [previewTarget, setPreviewTarget] = useState<PreviewTarget | null>(null);
  const [documents, drafts, packages] = useQueries({ queries: [
    { queryKey: ["documents"], queryFn: api.documents },
    { queryKey: ["material-drafts"], queryFn: () => api.materialDrafts() },
    { queryKey: ["application-packages"], queryFn: api.applicationPackages },
  ] });
  const programNames = useMemo(() => new Map((packages.data ?? []).map((item) => [item.program.id, `${item.program.university} · ${item.program.name}`])), [packages.data]);
  const allItems = useMemo(() => {
    const latestDrafts = new Map<string, MaterialDraft>();
    for (const draft of drafts.data ?? []) {
      const groupId = draft.root_id || draft.id;
      const current = latestDrafts.get(groupId);
      if (!current || draft.version_number > current.version_number) latestDrafts.set(groupId, draft);
    }
    return [
      ...(documents.data ?? []).map((item) => ({ id: item.id, type: "file" as const, kind: item.kind, name: item.filename, source: "上传文件", scope: "通用资源", status: item.parse_status, date: item.created_at, test: item.extracted_data.test_data === true })),
      ...Array.from(latestDrafts.values()).map((item) => ({ id: item.id, type: "draft" as const, kind: item.kind, name: `${item.title} · v${item.version_number}`, source: "AI 文稿", scope: item.program_id ? programNames.get(item.program_id) ?? "项目专用" : "通用资源", status: item.status === "reviewed" ? "已确认" : "草稿", date: item.updated_at, test: false })),
    ].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
  }, [documents.data, drafts.data, programNames]);
  const selectedCategory = categories.find((item) => item.value === filter) ?? categories[0];
  const items = useMemo(() => allItems.filter((item) => {
    const categoryMatches = filter === "all" || (filter === "ai" ? item.type === "draft" : selectedCategory.kinds.includes(item.kind));
    return categoryMatches && item.name.toLowerCase().includes(query.trim().toLowerCase());
  }), [allItems, filter, query, selectedCategory.kinds]);

  const upload = useMutation({ mutationFn: ({ file, kind }: { file: File; kind: string }) => api.uploadDocument(file, kind), onSuccess: (item) => { setNotice(`${item.filename} 已上传。`); client.invalidateQueries({ queryKey: ["documents"] }); client.invalidateQueries({ queryKey: ["application-packages"] }); }, onError: (error) => setNotice(error instanceof Error ? error.message : "上传失败") });
  const remove = useMutation({ mutationFn: api.deleteDocument, onSuccess: () => { setNotice("文件已从资源库删除。"); client.invalidateQueries({ queryKey: ["documents"] }); client.invalidateQueries({ queryKey: ["application-packages"] }); }, onError: (error) => setNotice(error instanceof Error ? error.message : "删除失败") });
  function onFile(event: ChangeEvent<HTMLInputElement>) { const file = event.target.files?.[0]; if (file) upload.mutate({ file, kind: uploadKind }); event.target.value = ""; }
  function preview(item: (typeof allItems)[number]) { setPreviewTarget({ type: item.type === "file" ? "document" : "draft", id: item.id, label: item.name }); }

  return <div className="mx-auto max-w-7xl">
    <PageHeader eyebrow="Personal files" title="材料资源库" description="统一管理申请过程中会反复使用的文件、历史文书版本和 AI 生成内容。" actions={<Link href="/assistant"><Button><Bot size={15} />打开 AI 助手</Button></Link>} />
    {notice && <div className="mb-5 rounded-xl border border-moss/10 bg-mint/70 px-4 py-3 text-sm font-bold text-moss">{notice}</div>}

    <Card className="overflow-hidden p-0">
      <div className="flex flex-col gap-3 border-b border-black/5 bg-white/70 p-4 lg:flex-row lg:items-center lg:justify-between">
        <label className="flex min-w-0 flex-1 items-center gap-2 rounded-xl border border-black/5 bg-paper/70 px-3 py-2.5 lg:max-w-md"><Search size={15} className="text-ink/35" /><input className="w-full bg-transparent text-sm outline-none" placeholder="搜索文件或文稿版本" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
        <div className="flex flex-wrap items-center gap-2"><select className="rounded-xl border border-black/5 bg-paper px-3 py-2.5 text-xs font-black outline-none" value={uploadKind} onChange={(event) => setUploadKind(event.target.value)}>{uploadKinds.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select><label className="inline-flex cursor-pointer items-center gap-2 rounded-xl bg-ink px-4 py-2.5 text-xs font-black text-white"><FileUp size={15} />{upload.isPending ? "正在上传…" : "上传文件"}<input type="file" className="hidden" onChange={onFile} disabled={upload.isPending} /></label></div>
      </div>

      <div className="grid min-h-[560px] md:grid-cols-[210px_1fr]">
        <aside className="border-b border-black/5 bg-paper/55 p-3 md:border-b-0 md:border-r">
          <p className="px-3 pb-2 pt-1 text-[10px] font-black uppercase tracking-[0.16em] text-ink/35">文件分类</p>
          <nav className="flex gap-1 overflow-x-auto md:block md:space-y-1">{categories.map((category) => { const count = allItems.filter((item) => category.value === "all" || (category.value === "ai" ? item.type === "draft" : category.kinds.includes(item.kind))).length; return <button key={category.value} type="button" onClick={() => setFilter(category.value)} className={cn("flex shrink-0 items-center gap-2 rounded-xl px-3 py-2.5 text-left text-xs font-black transition md:w-full", filter === category.value ? "bg-ink text-white" : "text-ink/55 hover:bg-mint/70")}><Folder size={15} /><span className="flex-1">{category.label}</span><span className={cn("text-[10px]", filter === category.value ? "text-white/45" : "text-ink/30")}>{count}</span></button>; })}</nav>
          <div className="mt-5 hidden rounded-2xl bg-mint/70 p-4 md:block"><Bot size={18} className="text-moss" /><p className="mt-3 text-xs font-black">需要新版本？</p><p className="mt-1 text-[10px] leading-5 text-ink/50">进入 AI 助手生成 CV、PS 或推荐信，结果会自动保存在这里。</p><Link href="/assistant" className="mt-3 flex items-center gap-1 text-[10px] font-black text-moss">开始生成 <ChevronRight size={12} /></Link></div>
        </aside>

        <main className="min-w-0 p-4 md:p-5">
          <div className="mb-4 flex items-end justify-between"><div><h2 className="text-lg font-black">{selectedCategory.label}</h2><p className="mt-1 text-xs text-ink/40">共 {items.length} 个文件或版本</p></div><p className="hidden text-[10px] text-ink/35 sm:block">正式提交文件建议使用 PDF</p></div>
          <div className="hidden grid-cols-[minmax(220px,1.5fr)_100px_minmax(130px,0.8fr)_110px_120px] gap-3 border-b border-black/5 px-3 pb-2 text-[10px] font-black text-ink/35 lg:grid"><span>文件名</span><span>类型</span><span>使用范围</span><span>更新时间</span><span className="text-right">操作</span></div>
          <div className="divide-y divide-black/5">{items.map((item) => <div key={`${item.type}:${item.id}`} className="grid gap-3 px-1 py-4 transition hover:bg-mint/20 sm:px-3 lg:grid-cols-[minmax(220px,1.5fr)_100px_minmax(130px,0.8fr)_110px_120px] lg:items-center">
            <button type="button" onClick={() => preview(item)} className="flex min-w-0 items-center gap-3 text-left"><span className={cn("grid size-10 shrink-0 place-items-center rounded-xl", item.type === "draft" ? "bg-violet-100 text-violet-700" : "bg-mint text-moss")}>{item.type === "draft" ? <Bot size={17} /> : <FileText size={17} />}</span><span className="min-w-0"><span className="block truncate text-sm font-black">{item.name}</span><span className="mt-1 flex items-center gap-2 text-[10px] text-ink/35"><span>{item.source}</span>{item.test && <span className="rounded-full bg-amber-100 px-1.5 py-0.5 font-black text-amber-800">测试数据</span>}<span>· {item.status}</span></span></span></button>
            <span className="w-fit rounded-full bg-paper px-2 py-1 text-[10px] font-black text-moss">{kindLabel[item.kind] ?? item.kind}</span>
            <span className="truncate text-xs text-ink/50">{item.scope}</span>
            <span className="text-xs text-ink/40">{new Date(item.date).toLocaleDateString("zh-CN")}</span>
            <div className="flex justify-end gap-1"><Button size="sm" variant="ghost" aria-label="预览内容" onClick={() => preview(item)}><Eye size={14} /></Button>{item.type === "draft" && <Link href={`/library/drafts/${item.id}`}><Button size="sm" variant="ghost" aria-label="编辑文稿"><Pencil size={14} /></Button></Link>}<a href={item.type === "file" ? api.documentDownloadUrl(item.id) : api.materialDraftExportUrl(item.id, "pdf")} download><Button size="sm" variant="ghost" aria-label={item.type === "file" ? "下载文件" : "导出 PDF"}><Download size={14} /></Button></a>{item.type === "file" && <Button size="sm" variant="ghost" aria-label="删除文件" onClick={() => window.confirm(`确定删除 ${item.name} 吗？`) && remove.mutate(item.id)}><Trash2 size={14} /></Button>}</div>
          </div>)}</div>
          {!documents.isLoading && !drafts.isLoading && !items.length && <div className="py-20 text-center"><FileArchive className="mx-auto text-ink/20" size={38} /><p className="mt-4 font-black">没有符合条件的材料</p><p className="mt-1 text-sm text-ink/45">调整分类或搜索条件，也可以上传一个新文件。</p></div>}
        </main>
      </div>
    </Card>
    <MaterialPreviewDialog target={previewTarget} onClose={() => setPreviewTarget(null)} />
  </div>;
}
