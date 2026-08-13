"""Agent 记忆功能（精简版，仅依赖标准库，可直接运行）。

设计原则与 YYGlobal 的 `services/api/app/agent/memory.py` 保持一致：

- 只有「已确认」的信息才会沉淀为长期记忆，未确认的信息不会被当成事实；
- 记忆按 `key` 存储，新值取代旧值，但保留完整版本历史（可追溯）；
- 每条记忆都记录来源，保证可解释。

运行：`python Core-Agent/test_memory.py`
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

CONFIRMED_THRESHOLD = 0.8  # 置信度 >= 该值才视为「已确认」


@dataclass
class MemoryEntry:
    key: str
    value: dict
    source: str            # 来源类型，如 user_confirmed / official_website
    confidence: float
    memory_type: str = "semantic"   # semantic（事实）/ episodic（事件）
    active: bool = True
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class AgentMemory:
    """一个最小可用的 Agent 记忆：短期工作区 + 长期已确认记忆。"""

    def __init__(self) -> None:
        self._working: dict[str, Any] = {}                # 短期记忆：当前任务上下文，不持久化
        self._store: dict[str, list[MemoryEntry]] = {}    # 长期记忆：按 key 保存版本链

    # ---- 短期记忆（工作区）----
    def remember_working(self, key: str, value: Any) -> None:
        """记下当前任务的中间结果，任务结束即丢弃。"""
        self._working[key] = value

    def recall_working(self, key: str) -> Any:
        return self._working.get(key)

    # ---- 长期记忆 ----
    def add(self, key: str, value: dict, source: str, confidence: float) -> bool:
        """只有已确认的信息才会写入长期记忆，返回是否成功。"""
        if confidence < CONFIRMED_THRESHOLD:
            return False  # 未确认 → 不变成长期事实

        entry = MemoryEntry(key=key, value=value, source=source, confidence=confidence)
        # 新值取代旧值：把同 key 的历史版本都置为 inactive
        for old in self._store.get(key, []):
            old.active = False
        self._store.setdefault(key, []).append(entry)
        return True

    def get(self, key: str) -> dict | None:
        """返回当前生效（active）的记忆值。"""
        for entry in reversed(self._store.get(key, [])):
            if entry.active:
                return entry.value
        return None

    def history(self, key: str) -> list[MemoryEntry]:
        """返回某个 key 的完整版本历史。"""
        return list(self._store.get(key, []))


if __name__ == "__main__":
    m = AgentMemory()

    # 未确认的信息：不会写入长期记忆
    print(m.add("gpa", {"value": "3.9"}, source="guess", confidence=0.5))  # False
    print(m.get("gpa"))  # None

    # 已确认的信息：写入长期记忆
    m.add("gpa", {"value": "3.7"}, source="user_confirmed", confidence=1.0)
    print(m.get("gpa"))  # {'value': '3.7'}

    # 更新：新值取代旧值，但保留历史
    m.add("gpa", {"value": "3.8"}, source="transcript", confidence=0.95)
    print(m.get("gpa"))  # {'value': '3.8'}
    print(len(m.history("gpa")))  # 2
