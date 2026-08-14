"use client";

import { PageHeader } from "@/components/page-header";
import { ProcessGuide } from "@/components/process-guide";
import { Suspense } from "react";
import { ApplicationPackages } from "@/components/application-packages";
import { MaterialProjectSwitcher } from "@/components/material-project-switcher";
import { Button } from "@/components/ui/button";
import { Bot, Files } from "lucide-react";
import Link from "next/link";

export default function MaterialsPage() {
  return <div className="mx-auto max-w-7xl">
    <PageHeader eyebrow="Per-program workspace" title="申请材料准备" description="逐个项目查看官网材料要求，匹配历史版本，并完成需要生成、确认或补充的材料。" actions={<div className="flex flex-wrap gap-2"><Link href="/assistant"><Button variant="secondary"><Bot size={16} />AI 助手</Button></Link><Link href="/library"><Button variant="secondary"><Files size={16} />材料资源库</Button></Link></div>} />
    <ProcessGuide current={3} completed={[0, 1, 2]} />
    <Suspense fallback={<div className="rounded-2xl bg-white/65 px-6 py-16 text-center font-black">正在打开申请材料…</div>}>
      <MaterialProjectSwitcher />
      <ApplicationPackages />
    </Suspense>
  </div>;
}
