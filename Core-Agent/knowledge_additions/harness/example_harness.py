#!/usr/bin/env python3
"""示例 Harness：校验一个结构化任务计划（task plan）JSON 是否符合契约。

本工具是示例模版，用于印证 `SKILL_AND_HARNESS_THEORY.md` 中的 Harness 契约。
它校验的对象，正是 `skills/example-skill/SKILL.md` 所描述的产物。

校验规则（与该 Skill 的 Sanity Checks 一一对应）：
  - 顶层必须含 task_id（非空字符串）
  - 顶层必须含 goal（非空字符串）
  - 顶层必须含 status，取值属于 {planned, running, success, error}
  - 必须含 steps 数组，且长度 >= 1
  - 每个 step 必须含 step_id（非空字符串），且全局不重复
  - 每个 step 必须含 action（非空字符串）
  - 每个 step 必须含 tool（非空字符串）
  - 每个 step 必须含 order，为 >= 1 的整数

用法：
    python knowledge_additions/harness/example_harness.py path/to/plan.json
    python knowledge_additions/harness/example_harness.py --json-string '{"task_id":"p1",...}'
    python knowledge_additions/harness/example_harness.py path/to/plan.json --json

退出码：
    0  校验通过
    1  校验发现问题（契约不满足）
    2  输入不可读或 JSON 无效

仅依赖 Python 标准库。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# 与 Skill 的 status 取值保持一致——这是"互相印证"的关键。
VALID_STATUSES = {"planned", "running", "success", "error"}


def _is_non_empty_string(value: Any) -> bool:
    """判断 value 是否为非空字符串（去除首尾空白后非空）。"""
    return isinstance(value, str) and bool(value.strip())


def validate_task_plan(plan: Any) -> tuple[list[str], list[str]]:
    """校验一个任务计划对象，返回 (issues, warnings)。

    issues 会导致退出码 1；warnings 只提示，不影响通过。
    本函数为纯函数，不读写文件，便于单元测试。
    """
    issues: list[str] = []
    warnings: list[str] = []

    if not isinstance(plan, dict):
        issues.append("task plan 顶层必须是一个 JSON 对象")
        return issues, warnings

    # task_id
    if "task_id" not in plan:
        issues.append("缺少必填字段 'task_id'")
    elif not _is_non_empty_string(plan["task_id"]):
        issues.append("'task_id' 必须是非空字符串")

    # goal
    if "goal" not in plan:
        issues.append("缺少必填字段 'goal'")
    elif not _is_non_empty_string(plan["goal"]):
        issues.append("'goal' 必须是非空字符串")

    # status
    if "status" not in plan:
        issues.append("缺少必填字段 'status'")
    elif not _is_non_empty_string(plan["status"]):
        issues.append("'status' 必须是非空字符串")
    elif plan["status"] not in VALID_STATUSES:
        issues.append(
            f"'status' 取值非法：{plan['status']!r}，允许值为 {sorted(VALID_STATUSES)}"
        )

    # steps
    if "steps" not in plan:
        issues.append("缺少必填字段 'steps'")
        return issues, warnings
    steps = plan["steps"]
    if not isinstance(steps, list):
        issues.append("'steps' 必须是数组")
        return issues, warnings
    if len(steps) == 0:
        issues.append("'steps' 不能为空数组")

    seen_step_ids: set[str] = set()
    for idx, step in enumerate(steps, start=1):
        prefix = f"steps[{idx}]"
        if not isinstance(step, dict):
            issues.append(f"{prefix}: 必须是 JSON 对象")
            continue

        # step_id
        if "step_id" not in step:
            issues.append(f"{prefix}: 缺少 'step_id'")
        elif not _is_non_empty_string(step["step_id"]):
            issues.append(f"{prefix}: 'step_id' 必须是非空字符串")
        else:
            if step["step_id"] in seen_step_ids:
                issues.append(f"{prefix}: 'step_id' 重复：{step['step_id']!r}")
            seen_step_ids.add(step["step_id"])

        # action
        if "action" not in step:
            issues.append(f"{prefix}: 缺少 'action'")
        elif not _is_non_empty_string(step["action"]):
            issues.append(f"{prefix}: 'action' 必须是非空字符串")

        # tool
        if "tool" not in step:
            issues.append(f"{prefix}: 缺少 'tool'")
        elif not _is_non_empty_string(step["tool"]):
            issues.append(f"{prefix}: 'tool' 必须是非空字符串")

        # order
        if "order" not in step:
            issues.append(f"{prefix}: 缺少 'order'")
        else:
            order = step["order"]
            # 显式排除 bool，因为 bool 是 int 的子类
            if isinstance(order, bool) or not isinstance(order, int):
                issues.append(f"{prefix}: 'order' 必须是整数")
            elif order < 1:
                issues.append(f"{prefix}: 'order' 必须 >= 1，当前为 {order}")

    # 非致命提示：steps 的 order 不连续时给出 warning
    orders = [s.get("order") for s in steps if isinstance(s, dict) and isinstance(s.get("order"), int)]
    if orders and sorted(orders) != list(range(1, len(orders) + 1)):
        warnings.append("'steps' 的 order 不是从 1 开始的连续整数，请确认是否故意跳号")

    return issues, warnings


def _load_plan(path: Path) -> Any:
    """从文件读取并解析 JSON。"""
    # utf-8-sig 兼容带 BOM 的文件（与 Core-Agent 现有工具一致）
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def _format_text(issues: list[str], warnings: list[str]) -> str:
    """格式化人类可读输出。"""
    lines: list[str] = []
    for w in warnings:
        lines.append(f"[WARN] {w}")
    if issues:
        lines.append(f"[FAIL] 发现 {len(issues)} 个问题：")
        for i in issues:
            lines.append(f"  - {i}")
    else:
        lines.append("[PASS] 任务计划符合契约")
    return "\n".join(lines)


def _format_json(issues: list[str], warnings: list[str]) -> str:
    """格式化机器可读输出。"""
    return json.dumps(
        {
            "passed": len(issues) == 0,
            "issue_count": len(issues),
            "warning_count": len(warnings),
            "issues": issues,
            "warnings": warnings,
        },
        ensure_ascii=False,
        indent=2,
    )


def main(argv: list[str] | None = None) -> int:
    """命令行入口，返回退出码。"""
    parser = argparse.ArgumentParser(
        description="校验一个结构化任务计划 JSON 是否符合契约。"
    )
    parser.add_argument(
        "plan_file",
        nargs="?",
        type=Path,
        help="待校验的 task plan JSON 文件路径。",
    )
    parser.add_argument(
        "--json-string",
        help="内联 JSON 字符串（与 plan_file 二选一）。",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出结果，便于自动化消费。",
    )
    args = parser.parse_args(argv)

    # 解析输入
    plan: Any
    try:
        if args.json_string is not None:
            plan = json.loads(args.json_string)
        elif args.plan_file is not None:
            plan = _load_plan(args.plan_file)
        else:
            parser.error("必须提供 plan_file 或 --json-string 之一")
            return 2  # 不会真正执行到这里，保留以明确语义
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        message = f"输入不可读或 JSON 无效：{error}"
        if args.json:
            print(json.dumps({"passed": False, "error": message}, ensure_ascii=False))
        else:
            print(f"[ERROR] {message}", file=sys.stderr)
        return 2

    issues, warnings = validate_task_plan(plan)

    if args.json:
        print(_format_json(issues, warnings))
    else:
        print(_format_text(issues, warnings))

    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
