"use client";

import { useQuery } from "@tanstack/react-query";
import { Download, Eye, FileText, X } from "lucide-react";
import { API_URL, api } from "@/lib/api";
import { Button } from "@/components/ui/button";

export type PreviewTarget = { type: string; id: string; label: string };

export function MaterialPreviewDialog({ target, onClose }: { target: PreviewTarget | null; onClose: () => void }) {
  const preview = useQuery({ queryKey: ["material-preview", target?.type, target?.id], queryFn: () => api.materialAssetPreview(target!.type, target!.id), enabled: Boolean(target) });
  if (!target) return null;
  const item = preview.data;
  const rawUrl = item?.raw_url ? `${API_URL.replace(/\/api$/, "")}${item.raw_url}` : "";
  const visual = item?.mime_type.startsWith("image/") || item?.mime_type === "application/pdf";
  return <div className="fixed inset-0 z-[90] grid place-items-center bg-ink/65 p-3 backdrop-blur-sm sm:p-6" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
    <div className="flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-[24px] bg-white shadow-2xl">
      <div className="flex items-center justify-between gap-4 border-b border-black/5 px-5 py-4"><div className="flex min-w-0 items-center gap-3"><span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-mint text-moss"><Eye size={17} /></span><div className="min-w-0"><p className="truncate text-sm font-black">{item?.title ?? target.label}</p><p className="mt-0.5 text-[10px] text-ink/40">{item ? `${item.kind} · ${item.mime_type}` : "正在读取材料内容…"}</p></div></div><div className="flex gap-2">{rawUrl && <a href={rawUrl} download><Button size="sm" variant="secondary"><Download size={14} />下载原文件</Button></a>}<button type="button" aria-label="关闭预览" onClick={onClose} className="grid size-9 place-items-center rounded-full bg-paper"><X size={16} /></button></div></div>
      <div className="min-h-0 flex-1 overflow-auto bg-[#f5f3ed] p-4 sm:p-6">{preview.isLoading && <div className="grid min-h-[420px] place-items-center text-sm font-black text-ink/40">正在加载预览…</div>}{preview.isError && <div className="grid min-h-[420px] place-items-center text-sm font-black text-red-600">材料预览加载失败</div>}{item && visual && rawUrl && (item.mime_type.startsWith("image/") ? <img src={rawUrl} alt={item.title} className="mx-auto max-h-[72vh] rounded-xl bg-white object-contain shadow-soft" /> : <iframe title={item.title} src={rawUrl} className="h-[70vh] w-full rounded-xl border-0 bg-white shadow-soft" />)}{item && !visual && <div className="mx-auto max-w-3xl rounded-2xl bg-white p-6 shadow-soft"><div className="mb-5 flex items-center gap-2 border-b border-black/5 pb-4"><FileText size={17} className="text-moss" /><h2 className="font-black">{item.title}</h2></div><pre className="whitespace-pre-wrap break-words font-sans text-sm leading-7 text-ink/75">{item.content || "该文件暂时没有可提取的文本内容，请下载原文件查看。"}</pre></div>}</div>
    </div>
  </div>;
}
