"""Simple PR labeler: infer labels from a list of changed file paths.

This helper is intended to be lightweight and run with the Python standard
library. It implements a few pragmatic heuristics to suggest repository
labels (e.g. "frontend", "backend", "docs") based on file path substrings
and extensions.

Usage:
    # supply paths as CLI args
    python Core-Agent/pr_labeler.py apps/web/app/page.tsx services/api/app/main.py

    # or pipe a newline-delimited list
    git diff --name-only origin/main...HEAD | python Core-Agent/pr_labeler.py --stdin
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Iterable, List, Set


LABEL_RULES = {
    "frontend": ["apps/web", "components/", "tailwind", "next", "ui/", ".tsx", ".ts"],
    "backend": ["services/", "api/", "app/main.py", "alembic", ".py"],
    "docs": ["README", "docs/", ".md", "PRACTICE.md"],
    "tests": ["test_", "/tests/", "vitest", "unittest"],
    "infrastructure": ["Dockerfile", "docker-compose", "alembic", ".yml", ".yaml"],
    "security": ["scan_secrets", "audit", "secrets"],
    "agent": ["Core-Agent/", "Core-Agent\\"],
}


def infer_labels(paths: Iterable[str]) -> List[str]:
    """Return a sorted list of labels that match any of the supplied paths.

    Matching is simple substring matching (case-insensitive) which keeps the
    implementation dependency-free and predictable for CI use.
    """
    found: Set[str] = set()
    lower_paths = [p.lower() for p in paths]
    for label, keywords in LABEL_RULES.items():
        for kw in keywords:
            lw = kw.lower()
            for p in lower_paths:
                if lw in p:
                    found.add(label)
                    break
            if label in found:
                break

    # fall back to a generic label if nothing matched
    if not found:
        return ["other"]

    return sorted(found)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Infer PR labels from file paths")
    parser.add_argument("paths", nargs="*", help="changed file paths")
    parser.add_argument("--stdin", action="store_true", help="read newline-delimited paths from stdin")
    parser.add_argument("--json", action="store_true", help="output JSON list of labels")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths: List[str] = []
    if args.stdin:
        paths.extend(line.strip() for line in sys.stdin if line.strip())
    paths.extend(args.paths or [])

    if not paths:
        print("[ERROR] no paths provided", file=sys.stderr)
        return 2

    labels = infer_labels(paths)
    if args.json:
        print(json.dumps(labels))
    else:
        print(" ".join(labels))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
