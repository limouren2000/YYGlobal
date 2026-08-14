---
name: example-skill
description: "演示型方法论 Skill：教 Agent 如何把一个用户目标拆解为结构化任务计划（task plan），并产出可被 Harness 校验的 JSON 产物。用于学习 Skill 契约本身，可直接作为模版复制改名。"
---

# Example Skill：结构化任务计划生成

> 本 skill 是 **示例模版**，目的是印证 `SKILL_AND_HARNESS_THEORY.md` 中的 Skill 契约。
> 它同时是一个可用的方法论：教 Agent 把目标拆成结构化任务计划。

## Overview

**目标**：把用户给出的一个自然语言目标，拆解为一个结构化任务计划 JSON。

**典型流程**：

```
用户目标（自然语言）
  → 识别目标主体与边界
  → 拆解为有序步骤
  → 为每步标注工具与权限
  → 输出 task plan JSON
```

**典型输入**：

```text
"帮我查某公司最近一周的舆情并写一份摘要"
```

**典型输出**（即 Harness 校验对象）：

```json
{
  "task_id": "plan-2026-08-13-001",
  "goal": "查某公司最近一周舆情并写摘要",
  "status": "planned",
  "steps": [
    {"step_id": "s1", "action": "web_search", "tool": "search_api", "order": 1},
    {"step_id": "s2", "action": "summarize", "tool": "llm", "order": 2}
  ]
}
```

> ⚠️ 该输出 JSON 的字段，正是同目录 `harness/example_harness.py` 的校验对象。
> Skill 的 Sanity Checks 与 Harness 的校验项一一对应，这就是"互相印证"。

## 关键概念

### 1. 目标边界化

先把模糊目标收敛成一句可验证的 goal：

- 主语是谁？
- 时间范围是什么？
- 交付物是什么？

### 2. 步骤有序化

每个步骤必须有 `step_id` 与 `order`，便于后续 Harness 检查顺序与重复。

### 3. 工具显式化

每步标注 `tool`，让计划可被权限策略（tool-policy）审查。

## 代码模板：生成任务计划

```python
import json
from datetime import datetime, timezone


def build_task_plan(goal: str, steps: list[dict]) -> dict:
    """根据目标与步骤列表，构造一个结构化任务计划。

    本函数只做结构封装，不做语义判断——语义校验交给 Harness。
    """
    plan = {
        "task_id": f"plan-{datetime.now(timezone.utc).strftime('%Y-%m-%d-%H%M%S')}",
        "goal": goal,
        "status": "planned",
        "steps": [],
    }
    for idx, step in enumerate(steps, start=1):
        plan["steps"].append({
            "step_id": step.get("step_id", f"s{idx}"),
            "action": step["action"],
            "tool": step["tool"],
            "order": step.get("order", idx),
        })
    return plan


if __name__ == "__main__":
    plan = build_task_plan(
        goal="查某公司最近一周舆情并写摘要",
        steps=[
            {"step_id": "s1", "action": "web_search", "tool": "search_api"},
            {"step_id": "s2", "action": "summarize", "tool": "llm"},
        ],
    )
    print(json.dumps(plan, ensure_ascii=False, indent=2))
```

## Common Mistakes

- **task_id 为空或重复。** 纠正：每次生成必须带唯一 `task_id`，建议含时间戳。
- **status 用了未约定值。** 纠正：只允许 `planned / running / success / error`，与 Harness 枚举一致。
- **steps 为空数组。** 纠正：一个计划至少要有 1 个步骤，否则无意义。
- **order 出现负数或重复。** 纠正：`order` 为正整数，建议从 1 递增。
- **把校验逻辑写进 Skill。** 纠正：Skill 只负责生成，校验归 Harness。

## Sanity Checks

> 以下每一项都对应 `harness/example_harness.py` 的一条校验规则。

- [ ] 顶层含 `task_id`，且为非空字符串
- [ ] 顶层含 `goal`，且为非空字符串
- [ ] 顶层含 `status`，取值属于 `{planned, running, success, error}`
- [ ] 含 `steps` 数组，且长度 ≥ 1
- [ ] 每个 step 含 `step_id`（非空字符串）且不重复
- [ ] 每个 step 含 `action`（非空字符串）
- [ ] 每个 step 含 `tool`（非空字符串）
- [ ] 每个 step 含 `order`，为 ≥ 1 的整数
