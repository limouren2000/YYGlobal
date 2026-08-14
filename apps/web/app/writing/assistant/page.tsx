"use client";

import { useEffect } from "react";

export default function LegacyWritingAssistantPage() {
  useEffect(() => {
    window.location.replace(`/assistant${window.location.search}`);
  }, []);
  return <div className="grid min-h-[60vh] place-items-center text-sm font-bold text-ink/45">正在打开 YYGlobal AI 助手…</div>;
}
