"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Bot,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Eye,
  ExternalLink,
  FileText,
  FolderOpen,
  RefreshCw,
  Upload,
  UserRound,
  X,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  MaterialPreviewDialog,
  PreviewTarget,
} from "@/components/material-preview-dialog";
import { api, ApplicationPackage, PackageMaterial } from "@/lib/api";
import { cn } from "@/lib/utils";

const generatable = new Set(["cv", "ps", "recommendation"]);
const categoryLabel: Record<string, string> = {
  cv: "CV",
  ps: "项目文书",
  recommendation: "推荐信",
};

function Pill({
  tone,
  children,
}: {
  tone: "ready" | "work" | "missing";
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-black",
        tone === "ready"
          ? "bg-emerald-100 text-emerald-800"
          : tone === "missing"
            ? "bg-red-100 text-red-700"
            : "bg-amber-100 text-amber-800",
      )}
    >
      {children}
    </span>
  );
}

export function ApplicationPackages() {
  const client = useQueryClient();
  const searchParams = useSearchParams();
  const programId = searchParams.get("program") ?? "";
  const [notice, setNotice] = useState("");
  const [historyRow, setHistoryRow] = useState<PackageMaterial | null>(null);
  const [historyAsset, setHistoryAsset] = useState("");
  const [previewTarget, setPreviewTarget] = useState<PreviewTarget | null>(
    null,
  );
  const packages = useQuery({
    queryKey: ["application-packages"],
    queryFn: api.applicationPackages,
  });
  const pack = packages.data?.find((item) => item.program.id === programId);
  const refresh = useMutation({
    mutationFn: api.refreshApplicationPackage,
    onSuccess: () => {
      setNotice("已重新匹配画像、初始材料和历史版本。");
      client.invalidateQueries({ queryKey: ["application-packages"] });
    },
  });
  const update = useMutation({
    mutationFn: ({
      item,
      asset,
      status,
    }: {
      item: PackageMaterial;
      asset: string;
      status: PackageMaterial["status"];
    }) => {
      const separator = asset.indexOf(":");
      const selected_asset_type =
        separator >= 0 ? asset.slice(0, separator) : "";
      const selected_asset_id =
        separator >= 0 ? asset.slice(separator + 1) : "";
      if (!pack) throw new Error("申请包不存在");
      return api.updatePackageMaterial(pack.id, {
        material_key: item.material_key,
        status,
        selected_asset_type,
        selected_asset_id,
        note: "由用户在项目申请包中确认",
      });
    },
    onSuccess: (result) => {
      setHistoryRow(null);
      setHistoryAsset("");
      setNotice("申请包已保存。下次进入该项目时会继续显示当前进度。");
      client.setQueryData<ApplicationPackage[]>(
        ["application-packages"],
        (rows = []) => rows.map((row) => (row.id === result.id ? result : row)),
      );
      client.invalidateQueries({ queryKey: ["application-packages"] });
    },
    onError: (error) =>
      setNotice(error instanceof Error ? error.message : "保存失败"),
  });
  const confirmPlan = useMutation({
    mutationFn: () => {
      if (!pack) throw new Error("申请包不存在");
      return api.confirmPackagePlan(pack.id);
    },
    onSuccess: (result) => {
      setNotice("本项目材料方案已确认，可以进入申请看板。");
      client.setQueryData<ApplicationPackage[]>(
        ["application-packages"],
        (rows = []) => rows.map((row) => (row.id === result.id ? result : row)),
      );
    },
    onError: (error) =>
      setNotice(error instanceof Error ? error.message : "方案确认失败"),
  });

  const groups = useMemo(() => {
    const rows = pack?.checklist ?? [];
    return {
      matched: rows.filter(
        (row) =>
          !generatable.has(row.category ?? row.material_key) &&
          row.candidate_assets.length > 0,
      ),
      core: rows.filter((row) =>
        generatable.has(row.category ?? row.material_key),
      ),
      missing: rows.filter(
        (row) =>
          !generatable.has(row.category ?? row.material_key) &&
          !row.candidate_assets.length,
      ),
    };
  }, [pack]);

  if (!programId) return null;
  if (packages.isLoading || !pack)
    return (
      <Card className="py-16 text-center">
        <RefreshCw className="mx-auto animate-spin text-moss" />
        <p className="mt-3 font-black">正在打开申请材料…</p>
      </Card>
    );

  const completed = pack.checklist.filter(
    (row) => row.status === "ready",
  ).length;
  return (
    <>
      <div className="mb-5 flex items-center justify-between gap-3">
        <div>
          <Link
            href="/shortlist"
            className="inline-flex items-center gap-2 text-sm font-bold text-ink/55"
          >
            <ArrowLeft size={15} />
            返回选校清单
          </Link>
          <p className="mt-2 text-xs text-ink/35">
            选校清单 <ChevronRight className="inline" size={12} />{" "}
            {pack.program.university}{" "}
            <ChevronRight className="inline" size={12} /> 申请材料
          </p>
        </div>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => refresh.mutate(pack.program.id)}
          disabled={refresh.isPending}
        >
          <RefreshCw size={14} />
          重新匹配资源
        </Button>
      </div>
      {notice && (
        <div className="mb-5 rounded-xl bg-mint/70 px-4 py-3 text-sm text-moss">
          {notice}
        </div>
      )}
      <section className="overflow-hidden rounded-[28px] bg-ink text-white">
        <div className="grid gap-6 p-6 md:grid-cols-[1fr_250px] md:p-8">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.18em] text-emerald-300">
              {pack.program.university}
            </p>
            <h1 className="mt-3 text-2xl font-black">{pack.program.name}</h1>
            <p className="mt-3 text-sm text-white/55">
              系统根据官网要求匹配你的画像和历史资源。选择与确认状态会持续保存。
            </p>
            <a
              href={pack.program.official_url}
              target="_blank"
              rel="noreferrer"
              className="mt-5 inline-flex items-center gap-1 text-xs font-bold text-emerald-300"
            >
              项目官网 <ExternalLink size={13} />
            </a>
          </div>
          <div className="rounded-2xl bg-white/10 p-5">
            <div className="flex items-end justify-between">
              <div>
                <p className="text-xs text-white/45">完成度</p>
                <strong className="mt-1 block text-3xl">
                  {completed}/{pack.checklist.length}
                </strong>
              </div>
              <span className="text-sm font-black text-emerald-300">
                {pack.checklist.length
                  ? Math.round((completed / pack.checklist.length) * 100)
                  : 0}
                %
              </span>
            </div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/10">
              <div
                className="h-full bg-emerald-300"
                style={{
                  width: `${pack.checklist.length ? (completed / pack.checklist.length) * 100 : 0}%`,
                }}
              />
            </div>
          </div>
        </div>
      </section>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_290px]">
        <main className="space-y-6">
          <Card className="border-blue-100">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="eyebrow">Official requirements</p>
                <h2 className="mt-2 text-xl font-black">官网材料清单</h2>
                <p className="mt-1 text-sm text-ink/50">
                  后续匹配、生成和缺失项都以这份清单为准。
                </p>
              </div>
            </div>
            <div className="mt-5 divide-y divide-black/5">
              {pack.checklist.map((row) => (
                <div
                  key={row.material_key}
                  className="grid gap-2 py-3 sm:grid-cols-[1fr_180px] sm:items-center"
                >
                  <div>
                    <p className="text-sm font-black">
                      {row.official_name || row.name}
                    </p>
                    <p className="mt-1 text-xs text-ink/40">
                      {row.required ? "必需材料" : "可选材料"}
                    </p>
                  </div>
                  <div className="sm:text-right">
                    <Pill
                      tone={
                        row.status === "ready"
                          ? "ready"
                          : row.candidate_assets.length
                            ? "work"
                            : "missing"
                      }
                    >
                      {row.status === "ready"
                        ? pack.plan_confirmed
                          ? "方案已确认"
                          : "已有当前方案"
                        : row.candidate_assets.length
                          ? "需要处理"
                          : "缺少"}
                    </Pill>
                  </div>
                </div>
              ))}
            </div>
            {pack.program.evidence.length > 0 && (
              <details className="mt-4 rounded-xl bg-blue-50 p-3">
                <summary className="cursor-pointer text-xs font-black text-blue-800">
                  查看官网原文证据（{pack.program.evidence.length}）
                </summary>
                <div className="mt-3 space-y-2">
                  {pack.program.evidence.map((item) => (
                    <blockquote
                      key={item.id}
                      className="border-l-2 border-blue-200 pl-3 text-xs leading-5 text-ink/55"
                    >
                      {item.quote}
                    </blockquote>
                  ))}
                </div>
              </details>
            )}
          </Card>

          {!!groups.matched.length && (
            <Card className="border-emerald-100">
              <div className="flex items-start justify-between">
                <div>
                  <p className="eyebrow">Auto-matched</p>
                  <h2 className="mt-2 text-xl font-black">
                    已从画像与资源库匹配
                  </h2>
                </div>
                <Pill tone="ready">{groups.matched.length} 项有资源</Pill>
              </div>
              <div className="mt-4 divide-y divide-black/5">
                {groups.matched.map((row) => {
                  const chosen = row.candidate_assets.find(
                    (asset) =>
                      asset.type === row.selected_asset_type &&
                      asset.id === row.selected_asset_id,
                  );
                  return (
                    <div
                      key={row.material_key}
                      className="grid gap-3 py-4 sm:grid-cols-[150px_1fr_auto] sm:items-center"
                    >
                      <div className="flex items-center gap-2 font-black">
                        <span className="grid size-8 place-items-center rounded-xl bg-emerald-100 text-emerald-700">
                          <Check size={14} />
                        </span>
                        {row.name}
                      </div>
                      <div>
                        <p className="text-sm font-bold">
                          {chosen?.label ?? "尚未形成当前方案"}
                        </p>
                        <p className="mt-1 text-xs text-ink/40">
                          {chosen
                            ? row.candidate_assets.length === 1
                              ? "唯一候选，已自动采用"
                              : "系统已推荐一个版本"
                            : "需要选择一个版本"}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        {chosen && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() =>
                              setPreviewTarget({
                                type: chosen.type,
                                id: chosen.id,
                                label: chosen.label,
                              })
                            }
                          >
                            <Eye size={14} />
                            预览
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => {
                            setHistoryAsset(
                              chosen ? `${chosen.type}:${chosen.id}` : "",
                            );
                            setHistoryRow(row);
                          }}
                        >
                          {chosen ? "更换版本" : "选择版本"}
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          )}

          {!!groups.core.length && (
            <section>
              <div className="mb-4 flex items-end justify-between">
                <div>
                  <p className="eyebrow">Recommended plan</p>
                  <h2 className="mt-2 text-2xl font-black">核心材料当前方案</h2>
                  <p className="mt-1 text-sm text-ink/50">
                    系统先形成默认方案；你只需要处理缺失项或更换不合适的版本。
                  </p>
                </div>
              </div>
              {["cv", "ps", "recommendation"].map((category) => {
                const rows = groups.core.filter(
                  (row) => (row.category ?? row.material_key) === category,
                );
                if (!rows.length) return null;
                return (
                  <div
                    key={category}
                    className="mb-4 rounded-2xl border border-black/5 bg-white/45 p-4"
                  >
                    <div className="mb-3 flex items-center gap-2">
                      <span className="grid size-9 place-items-center rounded-xl bg-paper text-moss">
                        {category === "recommendation" ? (
                          <UserRound size={16} />
                        ) : (
                          <FileText size={16} />
                        )}
                      </span>
                      <div>
                        <h3 className="font-black">
                          {categoryLabel[category]}
                        </h3>
                        <p className="text-xs text-ink/40">
                          {rows.filter((row) => row.selected_asset_id).length}/
                          {rows.length} 已形成方案
                        </p>
                      </div>
                    </div>
                    <div className="space-y-3">
                      {rows.map((row) => {
                        const current = row.candidate_assets.find(
                          (asset) =>
                            asset.type === row.selected_asset_type &&
                            asset.id === row.selected_asset_id,
                        );
                        return (
                          <Card
                            key={row.material_key}
                            className="grid gap-3 p-4 shadow-none md:grid-cols-[1fr_auto] md:items-center"
                          >
                            <div>
                              <div className="flex flex-wrap items-center gap-2">
                                <p className="text-sm font-black">{row.name}</p>
                                {current ? (
                                  <Pill tone="ready">
                                    <CheckCircle2 size={12} />
                                    {row.candidate_assets.length === 1
                                      ? "已自动匹配"
                                      : "系统推荐"}
                                  </Pill>
                                ) : (
                                  <Pill tone="work">需要处理</Pill>
                                )}
                              </div>
                              {current ? (
                                <>
                                  <p className="mt-2 text-sm font-bold text-moss">
                                    当前方案：{current.label}
                                  </p>
                                  <p className="mt-1 text-xs text-ink/40">
                                    {row.candidate_assets.length === 1
                                      ? "仅有一个对应版本，已直接采用。"
                                      : "已从多个候选中推荐一个版本，你可以预览或更换。"}
                                  </p>
                                </>
                              ) : (
                                <p className="mt-2 text-xs text-ink/45">
                                  {category === "ps" &&
                                  row.candidate_assets.length
                                    ? "现有通用文书仅作为参考，请生成或选择当前项目专属版本。"
                                    : "还没有可直接采用的版本。"}
                                </p>
                              )}
                            </div>
                            <div className="flex flex-wrap gap-2">
                              {current && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() =>
                                    setPreviewTarget({
                                      type: current.type,
                                      id: current.id,
                                      label: current.label,
                                    })
                                  }
                                >
                                  <Eye size={14} />
                                  预览
                                </Button>
                              )}
                              <Button
                                size="sm"
                                variant="secondary"
                                onClick={() => {
                                  setHistoryAsset(
                                    current
                                      ? `${current.type}:${current.id}`
                                      : "",
                                  );
                                  setHistoryRow(row);
                                }}
                              >
                                <FolderOpen size={14} />
                                {current ? "更换版本" : "选择历史版本"}
                              </Button>
                              <Link
                                href={`/assistant?program=${pack.program.id}&slot=${encodeURIComponent(row.slot_key ?? row.material_key)}`}
                              >
                                <Button size="sm">
                                  <Bot size={14} />让 AI 助手生成
                                </Button>
                              </Link>
                            </div>
                          </Card>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </section>
          )}

          {!!groups.missing.length && (
            <Card className="border-red-100">
              <div className="flex items-start justify-between">
                <div>
                  <p className="eyebrow">Missing</p>
                  <h2 className="mt-2 text-xl font-black">缺少的材料</h2>
                </div>
                <Pill tone="missing">
                  <CircleAlert size={12} />
                  {groups.missing.length} 项
                </Pill>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {groups.missing.map((row) => (
                  <div
                    key={row.material_key}
                    className="rounded-xl border border-dashed border-red-200 bg-red-50/40 p-4"
                  >
                    <p className="font-black">{row.name}</p>
                    <p className="mt-1 text-xs text-ink/45">
                      资源库中没有找到对应材料。
                    </p>
                    <Link href="/library">
                      <Button className="mt-3" size="sm" variant="secondary">
                        <Upload size={14} />
                        前往资源库上传
                      </Button>
                    </Link>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </main>
        <aside className="space-y-4 xl:sticky xl:top-8 xl:self-start">
          <Card>
            <p className="eyebrow">Final review</p>
            <h2 className="mt-2 font-black">统一确认材料方案</h2>
            <p className="mt-2 text-xs leading-5 text-ink/50">
              无需逐项重复确认。检查当前方案后，在这里一次确认整个项目。
            </p>
            <div className="mt-4 space-y-2">
              {pack.gaps.slice(0, 6).map((gap) => (
                <p key={gap} className="rounded-lg bg-paper px-3 py-2 text-xs">
                  {gap}
                </p>
              ))}
            </div>
            <Button
              className="mt-4 w-full"
              onClick={() => confirmPlan.mutate()}
              disabled={
                confirmPlan.isPending ||
                pack.checklist.some((row) => !row.selected_asset_id)
              }
            >
              <Check size={15} />
              {pack.plan_confirmed ? "材料方案已确认" : "确认本项目材料方案"}
            </Button>
          </Card>
          <Link href="/applications">
            <Button className="h-12 w-full" disabled={!pack.ready}>
              进入申请看板 <ChevronRight size={15} />
            </Button>
          </Link>
        </aside>
      </div>

      {historyRow && (
        <div className="fixed inset-0 z-[70] grid place-items-center bg-ink/55 p-4">
          <div className="flex max-h-[88vh] w-full max-w-xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="flex shrink-0 items-start justify-between border-b border-black/5 px-5 py-4">
              <div className="min-w-0 pr-4">
                <p className="eyebrow">Resource library</p>
                <h2 className="mt-2 line-clamp-2 text-lg font-black">
                  为“{historyRow.name}”选择版本
                </h2>
                <p className="mt-1 text-xs text-ink/40">
                  共 {historyRow.candidate_assets.length} 个可用版本
                </p>
              </div>
              <button
                type="button"
                onClick={() => setHistoryRow(null)}
                className="grid size-9 place-items-center rounded-full bg-paper"
              >
                <X size={16} />
              </button>
            </div>
            <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-5 py-4 [scrollbar-gutter:stable]">
              {historyRow.candidate_assets.map((asset) => (
                <div
                  key={`${asset.type}:${asset.id}`}
                  className={cn(
                    "flex items-center gap-2 rounded-xl border p-2",
                    historyAsset === `${asset.type}:${asset.id}`
                      ? "border-moss bg-mint/45"
                      : "border-black/5",
                  )}
                >
                  <button
                    type="button"
                    onClick={() => setHistoryAsset(`${asset.type}:${asset.id}`)}
                    className="flex min-w-0 flex-1 items-center gap-3 p-1 text-left"
                  >
                    <span
                      className={cn(
                        "grid size-5 shrink-0 place-items-center rounded-full border",
                        historyAsset === `${asset.type}:${asset.id}` &&
                          "border-moss bg-moss text-white",
                      )}
                    >
                      {historyAsset === `${asset.type}:${asset.id}` && (
                        <Check size={12} />
                      )}
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-black">
                        {asset.label}
                      </span>
                      <span className="text-xs text-ink/40">
                        {asset.type === "draft" ? "AI 文稿" : asset.type}
                        {asset.scope === "other_program" ? " · 其他项目版本" : ""}
                        {asset.status === "draft" ? " · 未确认草稿" : ""}
                      </span>
                    </span>
                  </button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() =>
                      setPreviewTarget({
                        type: asset.type,
                        id: asset.id,
                        label: asset.label,
                      })
                    }
                  >
                    <Eye size={14} />
                    预览
                  </Button>
                </div>
              ))}
              {!historyRow.candidate_assets.length && (
              <p className="rounded-xl bg-amber-50 p-4 text-sm text-amber-800">
                资源库中还没有可用历史版本，请使用 AI 助手生成。
              </p>
            )}
            </div>
            <div className="flex shrink-0 justify-end gap-2 border-t border-black/5 bg-white px-5 py-4">
              <Button variant="ghost" onClick={() => setHistoryRow(null)}>
                取消
              </Button>
              <Button
                disabled={!historyAsset}
                onClick={() =>
                  update.mutate({
                    item: historyRow,
                    asset: historyAsset,
                    status: "ready",
                  })
                }
              >
                采用这个版本
              </Button>
            </div>
          </div>
        </div>
      )}
      <MaterialPreviewDialog
        target={previewTarget}
        onClose={() => setPreviewTarget(null)}
      />
    </>
  );
}
