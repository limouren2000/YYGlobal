"use client";

import { useEffect } from "react";

export default function LegacyWritingPage() {
  useEffect(() => {
    const draftId = new URLSearchParams(window.location.search).get("draft");
    window.location.replace(draftId ? `/library/drafts/${draftId}` : "/library");
  }, []);
  return <div className="grid min-h-[60vh] place-items-center text-sm font-bold text-ink/45">正在打开材料资源库…</div>;
}
