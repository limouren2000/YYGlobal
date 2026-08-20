"""Material requirement normalizer：把官网抽取的材料要求归一成标准类别与资产槽位。

解决官网核验后材料清单里的两个实际问题：

1. 官网抽取常把整句原文当成「材料名」塞进清单，例如
   ``We request 3 letters, at least two of which are from faculty or recent
   employers.`` 本应归为「Recommendations」一行，却被原样展示。
2. ``English proficiency`` / ``GRE / GMAT`` 等官网用词无法映射到资产库槽位，
   导致申请包对应行恒显示「初始资产库中没有对应材料」。

零第三方依赖，可单独运行：

    python Core-Agent/material_normalizer.py --json '["We request 3 letters, at least two of which are from faculty or recent employers."]'
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

# 官网材料名 → 标准类别。关键词含 letters / reference(s) 等变体，避免漏匹配。
MATERIAL_CATEGORIES: dict[str, tuple[str, ...]] = {
    "CV / Resume": ("resume", "curriculum vitae", "cv"),
    "Statement of Purpose / Essays": ("statement of purpose", "personal statement", "essay"),
    "Transcripts": ("transcript",),
    "Recommendations": ("recommendation", "reference", "letters"),
    "English proficiency": ("toefl", "ielts", "english proficiency"),
    "GRE / GMAT": ("gre", "gmat"),
    "Portfolio": ("portfolio",),
}

# 标准类别 → 资产库槽位。English proficiency 归 language，GRE/GMAT 独立成 gre。
SLOT_BY_CATEGORY: dict[str, str] = {
    "CV / Resume": "cv",
    "Statement of Purpose / Essays": "ps",
    "Transcripts": "transcript",
    "Recommendations": "recommendation",
    "English proficiency": "language",
    "GRE / GMAT": "gre",
    "Portfolio": "portfolio",
}


def _keyword_pattern(keyword: str) -> str:
    """词边界 + 关键词 + 可选复数 s，兼容 transcripts/essays/letters 等复数。"""
    return rf"\b{re.escape(keyword)}s?\b"


def normalize_material_name(raw: str) -> str:
    """把单个材料名（可能是整句原文）归一成标准类别标签。

    无法映射时保留原样，便于人工发现未覆盖的非标准表述。
    """
    lowered = raw.lower()
    for category, keywords in MATERIAL_CATEGORIES.items():
        if any(re.search(_keyword_pattern(keyword), lowered) for keyword in keywords):
            return category
    return raw


def normalize_materials(materials: list[str]) -> list[str]:
    """把材料名列表逐条归一成标准类别并去重。"""
    normalized: list[str] = []
    for raw in materials:
        label = normalize_material_name(raw)
        if label not in normalized:
            normalized.append(label)
    return normalized


def material_slot(name: str) -> str:
    """把材料名归到资产库槽位；无法识别的名称返回 other_<slug> 以便排查。"""
    category = normalize_material_name(name)
    if category in SLOT_BY_CATEGORY:
        return SLOT_BY_CATEGORY[category]
    return "other_" + "_".join(name.lower().split())[:60]


class MaterialNormalizer:
    """归一化官网材料要求并映射到资产槽位。"""

    name = "material_normalizer"
    description = "把官网抽取的材料要求归一成标准类别，并映射到资产库槽位"

    def run(self, materials: list[str]) -> dict[str, Any]:
        normalized = normalize_materials(materials)
        return {
            "materials": normalized,
            "slots": {label: material_slot(label) for label in normalized},
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=MaterialNormalizer.description)
    parser.add_argument("--json", required=True, help="材料名列表的 JSON 数组字符串")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        materials = json.loads(args.json)
    except json.JSONDecodeError as exc:
        print(f"错误：--json 必须是合法 JSON 数组：{exc}", file=sys.stderr)
        return 1
    if not isinstance(materials, list) or not all(isinstance(m, str) for m in materials):
        print("错误：--json 必须是字符串数组", file=sys.stderr)
        return 1

    result = MaterialNormalizer().run(materials)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
