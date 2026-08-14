"""Scan the YYAbroad repository for hardcoded secrets and misconfigurations.

Security-audit style smoke test. Runs with only the standard library.

Usage:
    services/api/.venv/bin/python scripts/scan_secrets.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("API key (sk-*)", re.compile(r"\bsk-[A-Za-z0-9]{16,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("OpenAI key", re.compile(r"\bsk-proj-[A-Za-z0-9_-]{20,}\b")),
    ("Generic secret assignment", re.compile(r"(?:api[_-]?key|secret|password|token)\s*=\s*['\"][^'\"]{12,}['\"]", re.IGNORECASE)),
    ("Bearer token", re.compile(r"\bBearer\s+[A-Za-z0-9._-]{20,}\b")),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
]

SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "dist", "build", ".next"}
SKIP_SUFFIXES = (".lock", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf", ".woff", ".woff2", ".map")
IGNORE_PATHS = {".env.example", "pnpm-lock.yaml", "pyproject.toml", "Makefile", "docker-compose.yml"}
PLACEHOLDER_MARKERS = ("your", "example", "xxxx", "changeme", "<", "sk-你的")


def iter_target_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if not path.is_file() or path.suffix in SKIP_SUFFIXES or str(path.relative_to(ROOT)) in IGNORE_PATHS:
            continue
        try:
            path.read_bytes()
        except OSError:
            continue
        files.append(path)
    return files


def is_placeholder(value: str) -> bool:
    return any(marker in value.lower() for marker in PLACEHOLDER_MARKERS)


def scan_file(path: Path) -> list[str]:
    findings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return findings

    for label, pattern in SECRET_PATTERNS:
        for lineno, line in enumerate(text.splitlines(), start=1):
            match = pattern.search(line)
            if not match:
                continue
            hit = match.group(0)
            if is_placeholder(hit):
                continue
            findings.append(f"{path.relative_to(ROOT)}:{lineno} [{label}]")
    return findings


def check_gitignore() -> list[str]:
    issues: list[str] = []
    gitignore = ROOT / ".gitignore"
    if not gitignore.exists():
        return ["missing .gitignore"]
    content = gitignore.read_text(encoding="utf-8", errors="ignore")
    for required in (".env", ".env.*"):
        if required not in content:
            issues.append(f".gitignore does not ignore `{required}`")
    return issues


def main() -> None:
    findings: list[str] = []
    for file in iter_target_files():
        findings.extend(scan_file(file))
    findings.extend(check_gitignore())

    if findings:
        print(f"[FAIL] {len(findings)} potential issue(s) found:")
        for item in findings:
            print(f"  - {item}")
        sys.exit(1)

    print(f"[PASS] scanned {len(iter_target_files())} files, no secrets or config issues found")


if __name__ == "__main__":
    main()
