"use client";

import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Bookmark, BookmarkCheck, Bot, Check, Eye, FileText, FolderOpen, MessageSquarePlus, MoreVertical, PanelRight, Pencil, Pin, PinOff, Search, Send, Sparkles, Square, Trash2, Upload, UserRound, X } from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { MaterialPreviewDialog, PreviewTarget } from "@/components/material-preview-dialog";
import { api, AssistantConversation, MaterialDraft, streamAgent, WritingConversation } from "@/lib/api";
import { cn } from "@/lib/utils";

const sceneLabel: Record<string, string> = { application: "申请规划", cv: "CV", ps: "PS / Essay", recommendation: "推荐信" };
const defaultResources = ["profile", "confirmed_experiences", "official_requirements"];

export default function AssistantPage() {
  const client = useQueryClient();
  const conversations = useQuery({ queryKey: ["assistant-conversations"], queryFn: api.assistantConversations });
  const [packages, profile, documents, drafts] = useQueries({ queries: [
    { queryKey: ["application-packages"], queryFn: api.applicationPackages },
    { queryKey: ["profile"], queryFn: api.profile },
    { queryKey: ["documents"], queryFn: api.documents },
    { queryKey: ["material-drafts"], queryFn: () => api.materialDrafts() },
  ] });
  const [selectedId, setSelectedId] = useState("");
  const [programId, setProgramId] = useState("");
  const [slotKey, setSlotKey] = useState("");
  const [input, setInput] = useState("");
  const [notice, setNotice] = useState("");
  const [localMessages, setLocalMessages] = useState<Array<{ role: "user" | "assistant"; content: string; sources?: Array<Record<string, unknown>> }>>([]);
  const [pendingMaterialMessage, setPendingMaterialMessage] = useState<{ conversationId: string; content: string; sources: Array<Record<string, unknown>> } | null>(null);
  const [running, setRunning] = useState(false);
  const [menuId, setMenuId] = useState("");
  const [renamingId, setRenamingId] = useState("");
  const [renameValue, setRenameValue] = useState("");
  const [resourcePickerOpen, setResourcePickerOpen] = useState(false);
  const [resourceQuery, setResourceQuery] = useState("");
  const [previewTarget, setPreviewTarget] = useState<PreviewTarget | null>(null);
  const generationAbort = useRef<AbortController | null>(null);
  const activeGenerationConversationId = useRef("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setSelectedId(params.get("conversation") ?? "");
    setProgramId(params.get("program") ?? "");
    setSlotKey(params.get("slot") ?? "");
  }, []);

  const globalSelected = conversations.data?.find((item) => item.id === selectedId);
  useEffect(() => {
    if (globalSelected?.scene === "material" && (!programId || !slotKey)) {
      setProgramId(globalSelected.program_id ?? "");
      setSlotKey(globalSelected.slot_key);
    }
  }, [globalSelected, programId, slotKey]);
  const materialMode = Boolean(programId && slotKey);
  const programDetail = useQuery({ queryKey: ["program", programId], queryFn: () => api.program(programId), enabled: materialMode });
  const writingConversations = useQuery({
    queryKey: ["writing-conversations", programId, slotKey],
    queryFn: () => api.writingConversations(programId, slotKey),
    enabled: materialMode,
  });
  const pack = packages.data?.find((item) => item.program.id === programId);
  const slot = pack?.checklist.find((item) => (item.slot_key ?? item.material_key) === slotKey);
  const materialSelected = materialMode
    ? writingConversations.data?.find((item) => item.id === selectedId) ?? writingConversations.data?.[0]
    : undefined;
  const kind = (slot?.category ?? globalSelected?.material_kind ?? "ps") as "cv" | "ps" | "recommendation";

  useEffect(() => {
    if (materialMode && !selectedId && writingConversations.data?.length) setSelectedId(writingConversations.data[0].id);
  }, [materialMode, selectedId, writingConversations.data]);
  useEffect(() => {
    if (!materialMode) setLocalMessages(globalSelected?.messages.map((message) => ({ role: message.role, content: message.content, sources: message.sources })) ?? []);
  }, [globalSelected, materialMode]);

  function replaceLocation(values: { conversation?: string; program?: string; slot?: string }) {
    const params = new URLSearchParams();
    if (values.conversation) params.set("conversation", values.conversation);
    if (values.program) params.set("program", values.program);
    if (values.slot) params.set("slot", values.slot);
    window.history.replaceState(null, "", `/assistant${params.size ? `?${params.toString()}` : ""}`);
  }
  function openConversation(item: AssistantConversation) {
    setSelectedId(item.id);
    setNotice("");
    if (item.scene === "material") {
      setProgramId(item.program_id ?? "");
      setSlotKey(item.slot_key);
      replaceLocation({ conversation: item.id, program: item.program_id ?? "", slot: item.slot_key });
    } else {
      setProgramId(""); setSlotKey("");
      replaceLocation({ conversation: item.id });
    }
  }
  function newGeneralConversation() {
    setSelectedId(""); setProgramId(""); setSlotKey(""); setLocalMessages([]); setInput(""); setNotice("");
    replaceLocation({});
  }

  const manageConversation = useMutation({
    mutationFn: ({ id, values }: { id: string; values: { title?: string; pinned?: boolean; resource_ids?: string[] } }) => api.updateAssistantConversation(id, values),
    onSuccess: () => {
      setMenuId(""); setRenamingId(""); setRenameValue("");
      client.invalidateQueries({ queryKey: ["assistant-conversations"] });
      client.invalidateQueries({ queryKey: ["writing-conversations"] });
    },
    onError: (error) => setNotice(error instanceof Error ? error.message : "对话更新失败"),
  });
  const removeConversation = useMutation({
    mutationFn: (item: AssistantConversation) => api.deleteAssistantConversation(item.id).then(() => item),
    onSuccess: (item) => {
      setMenuId("");
      if (item.id === selectedId) {
        setSelectedId(""); setLocalMessages([]);
        if (item.scene === "material") replaceLocation({ program: item.program_id ?? "", slot: item.slot_key });
        else { setProgramId(""); setSlotKey(""); replaceLocation({}); }
      }
      client.invalidateQueries({ queryKey: ["assistant-conversations"] });
      client.invalidateQueries({ queryKey: ["writing-conversations"] });
    },
    onError: (error) => setNotice(error instanceof Error ? error.message : "删除对话失败"),
  });
  function beginRename(item: AssistantConversation) {
    setMenuId(""); setRenamingId(item.id); setRenameValue(item.title);
  }
  function submitRename(event: FormEvent, item: AssistantConversation) {
    event.preventDefault();
    const title = renameValue.trim();
    if (title && title !== item.title) manageConversation.mutate({ id: item.id, values: { title } });
    else { setRenamingId(""); setRenameValue(""); }
  }

  const createMaterial = useMutation({
    mutationFn: () => api.createWritingConversation({ program_id: programId, slot_key: slotKey, material_kind: kind, title: `${slot?.name ?? "项目文书"} · 新对话`, resource_ids: defaultResources }),
    onSuccess: (item) => {
      client.setQueryData<WritingConversation[]>(["writing-conversations", programId, slotKey], (rows = []) => [item, ...rows]);
      setSelectedId(item.id);
      replaceLocation({ conversation: item.id, program: programId, slot: slotKey });
      client.invalidateQueries({ queryKey: ["assistant-conversations"] });
    },
    onError: (error) => setNotice(error instanceof Error ? error.message : "新建对话失败"),
  });
  const sendMaterial = useMutation({
    mutationFn: async (message: string) => {
      const current = materialSelected ?? await api.createWritingConversation({ program_id: programId, slot_key: slotKey, material_kind: kind, title: `${slot?.name ?? "项目文书"} · 新对话`, resource_ids: defaultResources });
      if (!materialSelected) {
        client.setQueryData<WritingConversation[]>(["writing-conversations", programId, slotKey], (rows = []) => rows.some((row) => row.id === current.id) ? rows : [current, ...rows]);
        setSelectedId(current.id);
        replaceLocation({ conversation: current.id, program: programId, slot: slotKey });
      }
      setPendingMaterialMessage((pending) => ({ conversationId: current.id, content: message, sources: pending?.sources ?? [] }));
      const controller = new AbortController();
      generationAbort.current = controller;
      activeGenerationConversationId.current = current.id;
      try {
        return await api.sendWritingMessage(current.id, message, controller.signal);
      } finally {
        if (generationAbort.current === controller) generationAbort.current = null;
        if (activeGenerationConversationId.current === current.id) activeGenerationConversationId.current = "";
      }
    },
    onSuccess: (item) => {
      client.setQueryData<WritingConversation[]>(["writing-conversations", programId, slotKey], (rows = []) => rows.some((row) => row.id === item.id) ? rows.map((row) => row.id === item.id ? item : row) : [item, ...rows]);
      setSelectedId(item.id); setPendingMaterialMessage(null);
      replaceLocation({ conversation: item.id, program: programId, slot: slotKey });
      client.invalidateQueries({ queryKey: ["assistant-conversations"] });
      client.invalidateQueries({ queryKey: ["material-drafts"] });
    },
    onError: (error, message) => {
      setPendingMaterialMessage(null);
      setInput(message);
      client.invalidateQueries({ queryKey: ["writing-conversations", programId, slotKey] });
      setNotice(error instanceof DOMException && error.name === "AbortError" ? "已停止本次生成，消息已放回输入框。" : error instanceof Error ? error.message : "生成失败");
    },
  });
  const updateResources = useMutation({
    mutationFn: ({ id, resourceIds }: { id: string; resourceIds: string[] }) => api.updateWritingConversation(id, { resource_ids: resourceIds }),
    onSuccess: (item) => client.setQueryData<WritingConversation[]>(["writing-conversations", programId, slotKey], (rows = []) => rows.map((row) => row.id === item.id ? item : row)),
  });
  const attachResource = useMutation({
    mutationFn: async (resourceId: string) => {
      if (materialMode) {
        const current = materialSelected ?? await api.createWritingConversation({ program_id: programId, slot_key: slotKey, material_kind: kind, title: `${slot?.name ?? "项目文书"} · 新对话`, resource_ids: defaultResources });
        const next = current.resource_ids.includes(resourceId) ? current.resource_ids.filter((value) => value !== resourceId) : [...current.resource_ids, resourceId];
        return { mode: "material" as const, conversation: await api.updateWritingConversation(current.id, { resource_ids: next }) };
      }
      const current = globalSelected ?? await api.createAssistantConversation({ title: "带参考材料的新对话", resource_ids: [] });
      const next = current.resource_ids.includes(resourceId) ? current.resource_ids.filter((value) => value !== resourceId) : [...current.resource_ids, resourceId];
      return { mode: "application" as const, conversation: await api.updateAssistantConversation(current.id, { resource_ids: next }) };
    },
    onSuccess: ({ mode, conversation }) => {
      if (mode === "material") {
        client.setQueryData<WritingConversation[]>(["writing-conversations", programId, slotKey], (rows = []) => rows.some((row) => row.id === conversation.id) ? rows.map((row) => row.id === conversation.id ? conversation : row) : [conversation, ...rows]);
        replaceLocation({ conversation: conversation.id, program: programId, slot: slotKey });
      } else {
        client.setQueryData<AssistantConversation[]>(["assistant-conversations"], (rows = []) => rows.some((row) => row.id === conversation.id) ? rows.map((row) => row.id === conversation.id ? conversation : row) : [conversation, ...rows]);
        replaceLocation({ conversation: conversation.id });
      }
      setSelectedId(conversation.id);
      client.invalidateQueries({ queryKey: ["assistant-conversations"] });
    },
    onError: (error) => setNotice(error instanceof Error ? error.message : "引用材料失败"),
  });
  const uploadReference = useMutation({
    mutationFn: async (file: File) => {
      const document = await api.uploadDocument(file, "other");
      if (materialMode) {
        const current = materialSelected ?? await api.createWritingConversation({ program_id: programId, slot_key: slotKey, material_kind: kind, title: `${slot?.name ?? "项目文书"} · 新对话`, resource_ids: defaultResources });
        const conversation = await api.updateWritingConversation(current.id, { resource_ids: [...new Set([...current.resource_ids, `document:${document.id}`])] });
        return { document, mode: "material" as const, conversation };
      }
      const current = globalSelected ?? await api.createAssistantConversation({ title: `关于 ${document.filename} 的对话`, resource_ids: [] });
      const conversation = await api.updateAssistantConversation(current.id, { resource_ids: [...new Set([...current.resource_ids, `document:${document.id}`])] });
      return { document, mode: "application" as const, conversation };
    },
    onSuccess: ({ document, mode, conversation }) => {
      client.invalidateQueries({ queryKey: ["documents"] });
      if (mode === "material") {
        client.setQueryData<WritingConversation[]>(["writing-conversations", programId, slotKey], (rows = []) => rows.some((row) => row.id === conversation.id) ? rows.map((row) => row.id === conversation.id ? conversation : row) : [conversation, ...rows]);
        replaceLocation({ conversation: conversation.id, program: programId, slot: slotKey });
      } else {
        client.setQueryData<AssistantConversation[]>(["assistant-conversations"], (rows = []) => rows.some((row) => row.id === conversation.id) ? rows.map((row) => row.id === conversation.id ? conversation : row) : [conversation, ...rows]);
        replaceLocation({ conversation: conversation.id });
      }
      setSelectedId(conversation.id);
      client.invalidateQueries({ queryKey: ["assistant-conversations"] });
      setNotice(`${document.filename} 已上传到材料资源库并引用到当前对话。`);
    },
    onError: (error) => setNotice(error instanceof Error ? error.message : "上传失败"),
  });
  const confirm = useMutation({
    mutationFn: async (draftId: string) => {
      if (!pack || !slot) throw new Error("当前申请包不存在");
      const draft = drafts.data?.find((item) => item.id === draftId);
      const reviewed = draft?.status === "reviewed" ? draft : await api.updateMaterialDraft(draftId, { status: "reviewed" });
      await api.refreshApplicationPackage(programId);
      return api.updatePackageMaterial(pack.id, { material_key: slot.material_key, status: "ready", selected_asset_type: "draft", selected_asset_id: reviewed.id, note: `由 AI 对话 ${materialSelected?.id ?? selectedId} 生成并由用户确认` });
    },
    onSuccess: () => {
      setNotice("当前版本已确认并用于这个项目的申请包。");
      client.invalidateQueries({ queryKey: ["application-packages"] });
      client.invalidateQueries({ queryKey: ["writing-conversations", programId, slotKey] });
      client.invalidateQueries({ queryKey: ["assistant-conversations"] });
    },
    onError: (error) => setNotice(error instanceof Error ? error.message : "确认失败"),
  });

  function stopGeneration() {
    const conversationId = activeGenerationConversationId.current;
    generationAbort.current?.abort();
    if (conversationId) void api.cancelWritingGeneration(conversationId).catch(() => undefined);
    setRunning(false);
    setNotice("正在停止本次生成…");
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const value = input.trim();
    if (!value || running || sendMaterial.isPending) return;
    if (materialMode) {
      const outgoingSources = activeResourceIds.flatMap((resourceId) => resourceId.startsWith("document:") ? [{ type: "document", id: resourceId.slice(9) }] : resourceId.startsWith("draft:") ? [{ type: "reference_draft", id: resourceId.slice(6) }] : []);
      setInput("");
      setPendingMaterialMessage({ conversationId: materialSelected?.id ?? "", content: value, sources: outgoingSources });
      if (materialSelected) client.setQueryData<WritingConversation[]>(["writing-conversations", programId, slotKey], (rows = []) => rows.map((row) => row.id === materialSelected.id ? { ...row, resource_ids: row.resource_ids.filter((resourceId) => !resourceId.startsWith("document:") && !resourceId.startsWith("draft:")) } : row));
      sendMaterial.mutate(value);
      return;
    }
    const outgoingSources = activeResourceIds.flatMap((resourceId) => resourceId.startsWith("document:") ? [{ type: "document", id: resourceId.slice(9) }] : resourceId.startsWith("draft:") ? [{ type: "reference_draft", id: resourceId.slice(6) }] : []);
    setInput(""); setRunning(true); setLocalMessages((rows) => [...rows, { role: "user", content: value, sources: outgoingSources }]);
    if (globalSelected) client.setQueryData<AssistantConversation[]>(["assistant-conversations"], (rows = []) => rows.map((row) => row.id === globalSelected.id ? { ...row, resource_ids: [] } : row));
    const controller = new AbortController();
    generationAbort.current = controller;
    let conversationId = globalSelected?.id;
    try {
      await streamAgent(value, ({ event: name, data }) => {
        if (name === "run.started") { conversationId = String(data.conversation_id); setSelectedId(conversationId); replaceLocation({ conversation: conversationId }); }
        if (name === "message.completed") setLocalMessages((rows) => [...rows, { role: "assistant", content: String(data.content) }]);
      }, conversationId, controller.signal);
      client.invalidateQueries({ queryKey: ["assistant-conversations"] });
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) setLocalMessages((rows) => [...rows, { role: "assistant", content: error instanceof Error ? error.message : "AI 助手请求失败" }]);
      else setNotice("已停止本次生成。");
    } finally { if (generationAbort.current === controller) generationAbort.current = null; setRunning(false); }
  }

  const resourceOptions = useMemo<Array<{ id: string; label: string; meta: string; locked?: boolean }>>(() => [
    { id: "profile", label: "完整申请画像", meta: `${profile.data?.full_name || "申请人"} · ${profile.data?.current_major || "专业待补充"}` },
    { id: "official_requirements", label: "项目官网要求", meta: slot?.official_name || slot?.name || "当前材料要求", locked: true },
    ...(profile.data?.experiences.filter((item) => item.confirmed).map((item) => ({ id: `experience:${item.id}`, label: item.title || "已确认经历", meta: item.organization || item.kind })) ?? []),
  ], [profile.data, slot]);
  function toggleResource(resourceId: string) {
    if (resourceId === "official_requirements") return;
    if (!materialSelected) { attachResource.mutate(resourceId); return; }
    const current = materialSelected.resource_ids.filter((value) => value !== "confirmed_experiences");
    const next = current.includes(resourceId) ? current.filter((value) => value !== resourceId) : [...current, resourceId];
    updateResources.mutate({ id: materialSelected.id, resourceIds: next });
  }
  const savedMessages = materialMode ? materialSelected?.messages ?? [] : localMessages;
  const showPendingMaterialMessage = Boolean(
    materialMode
    && pendingMaterialMessage
    && (!pendingMaterialMessage.conversationId || pendingMaterialMessage.conversationId === materialSelected?.id),
  );
  const messages = showPendingMaterialMessage
    ? [...savedMessages, { role: "user" as const, content: pendingMaterialMessage?.content ?? "", sources: pendingMaterialMessage?.sources ?? [] }]
    : savedMessages;
  const latestDrafts = useMemo(() => {
    const rows = new Map<string, MaterialDraft>();
    for (const draft of drafts.data ?? []) {
      const key = draft.root_id || draft.id;
      const current = rows.get(key);
      if (!current || draft.version_number > current.version_number) rows.set(key, draft);
    }
    return Array.from(rows.values());
  }, [drafts.data]);
  const libraryResources = useMemo(() => [
    ...(documents.data ?? []).map((item) => ({ resourceId: `document:${item.id}`, id: item.id, type: "document", label: item.filename, meta: item.kind || "上传文件" })),
    ...latestDrafts.map((item) => ({ resourceId: `draft:${item.id}`, id: item.id, type: "draft", label: `${item.title} · v${item.version_number}`, meta: `${item.kind.toUpperCase()} · ${item.status === "reviewed" ? "已确认" : "草稿"}` })),
  ], [documents.data, latestDrafts]);
  const filteredLibraryResources = libraryResources.filter((item) => item.label.toLowerCase().includes(resourceQuery.trim().toLowerCase()));
  const activeResourceIds = materialMode ? materialSelected?.resource_ids ?? [] : globalSelected?.resource_ids ?? [];
  const selectedLibraryResources = libraryResources.filter((item) => activeResourceIds.includes(item.resourceId));
  const officialEvidence = programDetail.data?.evidence.filter((item) => item.field === "materials") ?? [];
  const selectedPackageDraftId = slot?.selected_asset_type === "draft" ? slot.selected_asset_id : "";

  return <div className="fixed inset-0 z-40 flex bg-[#f7f5ef] lg:left-64">
    <aside className="hidden w-72 shrink-0 flex-col border-r border-black/5 bg-white/85 md:flex">
      <div className="border-b border-black/5 p-4"><Button className="w-full" onClick={newGeneralConversation}><MessageSquarePlus size={15} />新对话</Button></div>
      <div className="px-4 pt-5"><p className="text-[10px] font-black uppercase tracking-[0.16em] text-ink/35">全部历史对话</p><p className="mt-1 text-xs text-ink/45">申请分析与材料写作都在这里。</p></div>
      <nav className="mt-4 flex-1 space-y-1 overflow-y-auto px-3 pb-4">{conversations.data?.map((item) => renamingId === item.id ? <form key={item.id} onSubmit={(event) => submitRename(event, item)} className="flex items-center gap-1 rounded-xl border border-moss/30 bg-mint/45 p-2"><input autoFocus value={renameValue} onChange={(event) => setRenameValue(event.target.value)} className="min-w-0 flex-1 rounded-lg bg-white px-2 py-2 text-xs font-black outline-none" maxLength={240} /><button type="submit" className="grid size-8 place-items-center rounded-lg bg-ink text-white" aria-label="确认重命名"><Check size={14} /></button><button type="button" onClick={() => setRenamingId("")} className="grid size-8 place-items-center rounded-lg text-ink/45" aria-label="取消重命名"><X size={14} /></button></form> : <div key={item.id} className="group relative"><button type="button" onClick={() => openConversation(item)} className={cn("w-full rounded-xl px-3 py-3 pr-10 text-left", selectedId === item.id ? "bg-ink text-white" : "hover:bg-paper")}><div className="flex items-center gap-2"><span className={cn("rounded-full px-2 py-0.5 text-[9px] font-black", selectedId === item.id ? "bg-white/10 text-emerald-300" : item.scene === "material" ? "bg-violet-100 text-violet-700" : "bg-mint text-moss")}>{sceneLabel[item.material_kind || item.scene] ?? "AI 助手"}</span>{item.pinned && <Pin size={10} className={selectedId === item.id ? "text-emerald-300" : "text-moss"} />}<span className={cn("text-[9px]", selectedId === item.id ? "text-white/35" : "text-ink/30")}>{new Date(item.updated_at).toLocaleDateString("zh-CN")}</span></div><p className="mt-2 truncate text-xs font-black">{item.title}</p>{item.program_label && <p className={cn("mt-1 truncate text-[10px]", selectedId === item.id ? "text-white/45" : "text-ink/35")}>{item.program_label}</p>}</button><button type="button" onClick={() => setMenuId((value) => value === item.id ? "" : item.id)} className={cn("absolute right-2 top-2 grid size-7 place-items-center rounded-lg opacity-60 transition hover:opacity-100", selectedId === item.id ? "text-white hover:bg-white/10" : "text-ink/45 hover:bg-white")} aria-label="管理对话"><MoreVertical size={14} /></button>{menuId === item.id && <div className="absolute right-2 top-10 z-20 w-32 rounded-xl border border-black/5 bg-white p-1 shadow-xl"><button type="button" onClick={() => manageConversation.mutate({ id: item.id, values: { pinned: !item.pinned } })} className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-xs font-bold hover:bg-paper">{item.pinned ? <PinOff size={13} /> : <Pin size={13} />}{item.pinned ? "取消置顶" : "置顶"}</button><button type="button" onClick={() => beginRename(item)} className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-xs font-bold hover:bg-paper"><Pencil size={13} />重命名</button><button type="button" onClick={() => window.confirm(`确定删除对话“${item.title}”吗？生成的材料文件会保留。`) && removeConversation.mutate(item)} className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-xs font-bold text-red-600 hover:bg-red-50"><Trash2 size={13} />删除</button></div>}</div>)}{!conversations.data?.length && <p className="px-3 py-8 text-xs text-ink/40">还没有历史对话。</p>}</nav>
    </aside>

    <main className="flex min-w-0 flex-1 flex-col">
      <header className="flex min-h-16 items-center justify-between gap-3 border-b border-black/5 bg-white/75 px-4 py-3 sm:px-6"><div className="flex min-w-0 items-center gap-3"><span className={cn("grid size-10 shrink-0 place-items-center rounded-2xl", materialMode ? "bg-violet-100 text-violet-700" : "bg-ink text-emerald-300")}><Bot size={19} /></span><div className="min-w-0"><h1 className="text-sm font-black">YYGlobal AI 助手</h1><p className="truncate text-[11px] text-ink/40">{materialMode ? `${pack?.program.university ?? "当前项目"} · ${slot?.name ?? "材料写作"}` : globalSelected ? `${sceneLabel.application} · ${globalSelected.title}` : "开始一个新的申请对话"}</p></div></div><div className="flex shrink-0 gap-2">{materialMode && <><Link className="hidden sm:block" href={`/materials?program=${programId}`}><Button size="sm" variant="secondary"><ArrowLeft size={14} />返回申请包</Button></Link><Button size="sm" variant="secondary" className="hidden md:inline-flex" onClick={() => createMaterial.mutate()} disabled={createMaterial.isPending || sendMaterial.isPending}><MessageSquarePlus size={14} />新建此材料对话</Button></>}</div></header>
      {notice && <div className="mx-4 mt-4 rounded-xl bg-mint px-4 py-2 text-sm font-bold text-moss">{notice}</div>}
      <div className="flex-1 overflow-y-auto"><div className="mx-auto max-w-3xl px-4 py-8">
        {!messages.length && <div className="py-14 text-center"><span className={cn("mx-auto grid size-14 place-items-center rounded-2xl", materialMode ? "bg-violet-100 text-violet-700" : "bg-mint text-moss")}><Sparkles size={22} /></span><h2 className="mt-5 text-2xl font-black">{materialMode ? `完善 ${slot?.name ?? "申请材料"}` : "今天想继续处理什么？"}</h2><p className="mt-2 text-sm text-ink/45">{materialMode ? "已带入当前项目、官网要求和你的资源，直接告诉我这一版想突出什么。" : "可以分析项目、规划申请、整理经历，也可以从申请包进入具体材料写作。"}</p>{!materialMode && <div className="mx-auto mt-6 grid max-w-xl gap-2 sm:grid-cols-3">{["分析我的申请进度", "帮我比较已选项目", "规划下一步任务"].map((value) => <button type="button" key={value} onClick={() => setInput(value)} className="rounded-xl border border-black/5 bg-white px-3 py-3 text-xs font-bold hover:bg-mint">{value}</button>)}</div>}</div>}
        <div className="space-y-6">{messages.map((message, index) => {
          const messageSources = "sources" in message && Array.isArray(message.sources) ? message.sources as Array<Record<string, unknown>> : [];
          const draftSource = messageSources.find((source) => source.type === "draft" && typeof source.id === "string");
          const messageAttachments = messageSources.flatMap((source) => {
            if (typeof source.id !== "string" || !["document", "reference_draft"].includes(String(source.type))) return [];
            const resourceId = `${source.type === "document" ? "document" : "draft"}:${source.id}`;
            const resource = libraryResources.find((item) => item.resourceId === resourceId);
            return resource ? [resource] : [];
          });
          const messageDraftId = typeof draftSource?.id === "string" ? draftSource.id : "";
          const messageDraft = drafts.data?.find((item) => item.id === messageDraftId);
          const inPackage = Boolean(messageDraftId && selectedPackageDraftId === messageDraftId);
          const avatarClass = message.role === "assistant"
            ? (materialMode ? "bg-violet-100 text-violet-700" : "bg-mint text-moss")
            : "order-2 bg-ink text-white";
          return (
            <div key={String("id" in message ? message.id : index)} className={cn("flex gap-3", message.role === "user" && "justify-end")}>
              <span className={cn("grid size-8 shrink-0 place-items-center rounded-xl", avatarClass)}>
                {message.role === "assistant" ? <Bot size={15} /> : <UserRound size={15} />}
              </span>
              <div className={cn("max-w-[84%] overflow-hidden rounded-2xl text-sm leading-6", message.role === "assistant" ? "rounded-tl-md bg-white shadow-sm" : "rounded-tr-md bg-ink text-white")}>
                <div className="whitespace-pre-wrap px-4 py-3">{message.content}</div>
                {message.role === "user" && messageAttachments.length > 0 && <div className="flex flex-wrap justify-end gap-1.5 border-t border-white/10 px-3 py-2">{messageAttachments.map((resource) => <button type="button" key={resource.resourceId} onClick={() => setPreviewTarget({ type: resource.type, id: resource.id, label: resource.label })} className="inline-flex max-w-52 items-center gap-1.5 rounded-lg bg-white/10 px-2 py-1 text-[10px] font-bold text-white/80 hover:bg-white/20"><FileText size={11} /><span className="truncate">{resource.label}</span><Eye size={10} /></button>)}</div>}
                {materialMode && message.role === "assistant" && messageDraftId && (
                  <div className="flex flex-wrap items-center justify-between gap-2 border-t border-black/5 px-3 py-2">
                    {messageDraft ? (
                      <Link href={`/library/drafts/${messageDraft.id}`} className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[10px] font-black text-moss transition hover:bg-mint">
                        <FileText size={11} />文稿 v{messageDraft.version_number} · 查看全部版本
                      </Link>
                    ) : (
                      <span className="text-[10px] font-bold text-ink/35">本次生成的文稿</span>
                    )}
                    {inPackage ? (
                      <span className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-50 px-2.5 py-1 text-[10px] font-black text-emerald-700"><BookmarkCheck size={12} />申请包正在使用</span>
                    ) : (
                      <button type="button" disabled={confirm.isPending || drafts.isLoading || !messageDraft} onClick={() => confirm.mutate(messageDraftId)} className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[10px] font-black text-moss hover:bg-mint disabled:opacity-40">
                        <Bookmark size={12} />{confirm.isPending && confirm.variables === messageDraftId ? "正在采用…" : "采用此版本"}
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}{(running || sendMaterial.isPending) && <div className="flex items-center gap-3 text-sm font-bold text-ink/40"><span className="size-2 animate-pulse rounded-full bg-moss" />AI 助手正在处理，可随时停止</div>}</div>
      </div></div>
      <form onSubmit={submit} className="border-t border-black/5 bg-white/85 px-4 py-4">
        <div className="mx-auto max-w-3xl">
          <div className="rounded-2xl border border-black/10 bg-white p-2 shadow-soft">
            <div className="flex gap-2">
              <textarea className="min-h-12 min-w-0 flex-1 resize-none bg-transparent px-3 py-2 text-sm outline-none" value={input} onChange={(event) => setInput(event.target.value)} placeholder={materialMode ? "可以讨论思路，也可以明确要求生成或修改文稿…" : "询问申请规划、项目选择或下一步任务…"} />
              {running || sendMaterial.isPending ? <button type="button" onClick={stopGeneration} className="grid size-10 shrink-0 place-items-center self-end rounded-xl bg-red-600 text-white" aria-label="停止生成"><Square size={14} fill="currentColor" /></button> : <button type="submit" disabled={!input.trim()} className="grid size-10 shrink-0 place-items-center self-end rounded-xl bg-ink text-white disabled:opacity-35"><Send size={16} /></button>}
            </div>
            {selectedLibraryResources.length > 0 && <div className="flex flex-wrap gap-2 border-t border-black/5 px-2 pb-1 pt-2">{selectedLibraryResources.map((resource) => <span key={resource.resourceId} className="inline-flex max-w-full items-center gap-1.5 rounded-lg bg-paper px-2 py-1 text-[10px] font-bold text-ink/65"><FileText size={11} className="shrink-0 text-moss" /><span className="max-w-40 truncate">{resource.label}</span><button type="button" onClick={() => setPreviewTarget({ type: resource.type, id: resource.id, label: resource.label })} aria-label="预览材料"><Eye size={11} /></button><button type="button" onClick={() => attachResource.mutate(resource.resourceId)} aria-label="移除引用"><X size={11} /></button></span>)}</div>}
            <div className="flex flex-wrap items-center gap-2 border-t border-black/5 px-2 pt-2">
              <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg px-2 py-1.5 text-[10px] font-black text-ink/60 hover:bg-paper"><Upload size={12} />{uploadReference.isPending ? "上传中…" : "上传文件"}<input type="file" className="hidden" disabled={uploadReference.isPending} onChange={(event) => { const file = event.target.files?.[0]; if (file) uploadReference.mutate(file); event.target.value = ""; }} /></label>
              <button type="button" onClick={() => setResourcePickerOpen(true)} className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-[10px] font-black text-ink/60 hover:bg-paper"><FolderOpen size={12} />从资源库选择</button>
              <span className="ml-auto text-[9px] text-ink/30">附件会持续用于当前对话</span>
            </div>
          </div>
          {materialMode && <p className="mt-2 text-center text-[10px] text-ink/35">普通讨论不创建版本；生成完整材料或实际修改正文时才保存新版本</p>}
        </div>
      </form>
    </main>

    {materialMode && <aside className="hidden w-80 shrink-0 overflow-y-auto border-l border-black/5 bg-white/70 p-4 xl:block">
      <div className="flex items-center gap-2"><PanelRight size={16} /><h2 className="text-sm font-black">当前任务上下文</h2></div>
      <section className="mt-5 rounded-2xl bg-blue-50 p-4">
        <div className="flex items-center justify-between"><p className="text-xs font-black text-blue-900">官网要求</p><span className={cn("rounded-full px-2 py-0.5 text-[9px] font-black", programDetail.data?.requirement?.verified ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-800")}>{programDetail.data?.requirement?.verified ? "已核验" : "待核验"}</span></div>
        <p className="mt-2 text-sm font-bold leading-5">{slot?.official_name || "暂未获取到当前材料的具体官网要求"}</p>
        {officialEvidence.slice(0, 2).map((item) => <blockquote key={item.id} className="mt-3 border-l-2 border-blue-300 pl-3 text-[10px] leading-4 text-blue-950/60">{item.quote}</blockquote>)}
        {!officialEvidence.length && <p className="mt-2 text-[10px] leading-4 text-amber-800">当前没有可引用的官网原文证据，生成时不会把泛化说明当成确定要求。</p>}
        <a href={programDetail.data?.official_url || pack?.program.official_url} target="_blank" rel="noreferrer" className="mt-3 inline-block text-[10px] font-black text-blue-800 underline">查看项目官网</a>
      </section>
      <section className="mt-5">
        <div className="flex items-end justify-between"><p className="text-xs font-black">参考资源</p><span className="text-[10px] text-ink/35">会实际传入生成上下文</span></div>
        <div className="mt-3 space-y-2">{resourceOptions.map((resource) => { const active = Boolean(resource.locked) || materialSelected?.resource_ids.includes(resource.id) || (resource.id.startsWith("experience:") && materialSelected?.resource_ids.includes("confirmed_experiences")); return <button type="button" key={resource.id} disabled={Boolean(resource.locked) || updateResources.isPending || attachResource.isPending} onClick={() => toggleResource(resource.id)} className={cn("w-full rounded-xl border p-3 text-left transition", active ? "border-moss/30 bg-mint/60" : "border-black/5 bg-white hover:border-black/15", resource.locked && "cursor-default")}><div className="flex items-center gap-2"><span className={cn("grid size-4 place-items-center rounded border", active ? "border-moss bg-moss text-white" : "border-black/15")}>{active && <Check size={11} />}</span><p className="text-xs font-black">{resource.label}</p>{resource.locked && <span className="ml-auto rounded-full bg-white/70 px-2 py-0.5 text-[9px] font-black text-moss">每轮必读</span>}</div><p className="ml-6 mt-1 text-[10px] text-ink/40">{resource.meta}</p></button>; })}</div>
        {selectedLibraryResources.length > 0 ? <div className="mt-3 space-y-2">{selectedLibraryResources.map((resource) => <div key={resource.resourceId} className="flex items-center gap-2 rounded-xl bg-paper/80 p-2"><FileText size={13} className="shrink-0 text-moss" /><span className="min-w-0 flex-1 truncate text-[10px] font-bold">{resource.label}</span><button type="button" onClick={() => setPreviewTarget({ type: resource.type, id: resource.id, label: resource.label })} aria-label="预览材料"><Eye size={12} /></button></div>)}</div> : <p className="mt-3 text-[10px] leading-4 text-ink/35">当前没有引用文件；可在对话框下方添加。</p>}
      </section>
      <section className="mt-5"><p className="text-xs font-black">当前文稿版本</p>{materialSelected?.latest_draft ? <div className="mt-3 rounded-xl border border-emerald-100 bg-emerald-50 p-3"><p className="text-xs font-black">{materialSelected.latest_draft.title} v{materialSelected.latest_draft.version_number}</p><p className="mt-1 text-[10px] text-ink/40">{materialSelected.latest_draft.status === "reviewed" ? "已确认" : "待确认"}</p><Link href={`/library/drafts/${materialSelected.latest_draft.id}`}><Button className="mt-3 w-full" size="sm" variant="secondary"><FileText size={14} />编辑当前文稿</Button></Link></div> : <p className="mt-3 text-xs text-ink/40">开始对话后生成第一个版本。</p>}</section>
    </aside>}
    {resourcePickerOpen && <div className="fixed inset-0 z-[80] grid place-items-center bg-ink/60 p-4" onMouseDown={(event) => event.target === event.currentTarget && setResourcePickerOpen(false)}><div className="flex max-h-[82vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"><div className="flex items-center justify-between border-b border-black/5 p-5"><div><p className="eyebrow">Material library</p><h2 className="mt-1 text-lg font-black">选择对话参考材料</h2></div><button type="button" onClick={() => setResourcePickerOpen(false)} className="grid size-9 place-items-center rounded-full bg-paper"><X size={16} /></button></div><div className="border-b border-black/5 p-4"><label className="flex items-center gap-2 rounded-xl bg-paper px-3 py-2"><Search size={14} className="text-ink/35" /><input value={resourceQuery} onChange={(event) => setResourceQuery(event.target.value)} placeholder="搜索文件和历史文稿" className="w-full bg-transparent text-sm outline-none" /></label></div><div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-4">{filteredLibraryResources.map((resource) => { const active = activeResourceIds.includes(resource.resourceId); return <div key={resource.resourceId} className={cn("flex items-center gap-3 rounded-xl border p-3", active ? "border-moss/30 bg-mint/45" : "border-black/5")}><button type="button" onClick={() => attachResource.mutate(resource.resourceId)} className="flex min-w-0 flex-1 items-center gap-3 text-left"><span className={cn("grid size-5 place-items-center rounded border", active ? "border-moss bg-moss text-white" : "border-black/15")}>{active && <Check size={12} />}</span><span className="min-w-0"><span className="block truncate text-xs font-black">{resource.label}</span><span className="mt-1 block text-[10px] text-ink/40">{resource.meta}</span></span></button><Button size="sm" variant="ghost" onClick={() => setPreviewTarget({ type: resource.type, id: resource.id, label: resource.label })}><Eye size={13} />预览</Button></div>; })}{!filteredLibraryResources.length && <p className="py-12 text-center text-sm text-ink/40">没有符合条件的材料。</p>}</div><div className="flex justify-end border-t border-black/5 p-4"><Button onClick={() => setResourcePickerOpen(false)}>完成</Button></div></div></div>}
    <MaterialPreviewDialog target={previewTarget} onClose={() => setPreviewTarget(null)} />
  </div>;
}
