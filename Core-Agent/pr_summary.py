"""Create a Markdown PR summary for changes limited to ``Core-Agent/``.

Usage:
    python Core-Agent/pr_summary.py
    python Core-Agent/pr_summary.py --base origin/main
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from check_pr_scope import (
    ALLOWED_ROOT,
    GitError,
    collect_changed_paths,
    find_out_of_scope,
    find_repo_root,
    resolve_base_ref,
)


def render_pr_summary(changed_paths: set[str], base_ref: str) -> str:
    """Return a ready-to-paste Markdown PR description."""
    files = sorted(changed_paths)
    file_list = "\n".join(f"- `{path}`" for path in files)
    return "\n".join(
        (
            "## 变更说明",
            f"- 本次 PR 在 `{ALLOWED_ROOT}/` 中修改了 {len(files)} 个文件。",
            f"- 对比基线：`{base_ref}`。",
            "",
            "## 涉及文件",
            file_list,
            "",
            "## 验证",
            "- [ ] `python -m unittest discover -s Core-Agent -p \"test_*.py\"`",
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Markdown summary for a Core-Agent-only PR."
    )
    parser.add_argument(
        "--base",
        help="base branch or commit; defaults to the PR scope checker's detection order",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        repo_root = find_repo_root(Path.cwd())
        base_ref = resolve_base_ref(repo_root, args.base)
        changed_paths = collect_changed_paths(repo_root, base_ref)
    except (GitError, OSError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    if not changed_paths:
        print(f"[ERROR] no changes found relative to {base_ref}", file=sys.stderr)
        return 2

    invalid_paths = find_out_of_scope(changed_paths)
    if invalid_paths:
        print(f"[FAIL] PR contains files outside {ALLOWED_ROOT}/:", file=sys.stderr)
        for path in invalid_paths:
            print(f"  - {path}", file=sys.stderr)
        return 1

    print(render_pr_summary(changed_paths, base_ref))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
