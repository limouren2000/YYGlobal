助力每一个梦想，PR 请提交到这里。

## Skill contract audit

`audit_skill_contracts.py` validates every package under
`services/api/app/skills` before the API imports it. The audit checks required
files, frontmatter metadata, JSON Schema structure, evaluation cases, registered
tool names, and approval-policy consistency.

```bash
python Core-Agent/audit_skill_contracts.py
python Core-Agent/audit_skill_contracts.py --json
python -m unittest discover -s Core-Agent -p "test_*.py" -v
```

The command exits with `0` when all contracts pass, `1` when contract issues are
found, and `2` when the repository cannot be inspected. JSON output is suitable
for CI or other automation.

## Tool argument validation

`tool_arguments_validator.py` validates model-generated tool arguments with the
complete JSON Schema Draft 2020-12 implementation provided by `jsonschema`. It
checks nested objects and arrays, enums, numeric/string limits, required fields,
and additional-property rules instead of relying
on shallow top-level type checks.

Run it in the API development environment, where `jsonschema` is already a
declared dependency:

```bash
services/api/.venv/bin/python Core-Agent/tool_arguments_validator.py \
  --schema path/to/tool.schema.json \
  --arguments path/to/arguments.json
```

Use inline arguments and JSON output in automation:

```bash
services/api/.venv/bin/python Core-Agent/tool_arguments_validator.py \
  --schema path/to/tool.schema.json \
  --arguments-json '{"program_ids":["program-1"]}' \
  --json
```

Exit codes are `0` for valid arguments, `1` for schema violations, and `2` for
an invalid schema or unreadable JSON input. Python callers can import
`validate_tool_arguments` for structured issues or
`require_valid_tool_arguments` for an exception-based gate.

## Agent trace validation

`agent_trace_validator.py` checks a compact, framework-agnostic JSONL event
contract. It validates required fields, statuses, durations, step relationships,
and event ordering within each trace. Regular UTF-8 and UTF-8 files with a byte
order mark (BOM) are supported.

```bash
python Core-Agent/agent_trace_validator.py path/to/trace.jsonl
python -m unittest Core-Agent/test_agent_trace_validator.py -v
```

The command exits with `0` for a valid trace, `1` for validation findings, and
`2` when the input cannot be read.

## Official evidence bundle audit

`evidence_bundle_auditor.py` checks an exported program-research evidence
bundle before an Agent cites it. It validates HTTPS official sources, source
status and freshness, evidence-to-source references, quotes, confidence values,
and coverage for critical fields. By default, both `deadline` and `materials`
must have valid evidence from a verified official source.

```bash
python Core-Agent/evidence_bundle_auditor.py evidence.json
python Core-Agent/evidence_bundle_auditor.py evidence.json \
  --required-fields deadline,materials,tuition \
  --max-age-days 60 \
  --as-of 2026-08-13 \
  --json
python -m unittest Core-Agent/test_evidence_bundle_auditor.py -v
```

Warnings such as stale sources do not fail the audit. Contract errors or
missing verified evidence exit with `1`; unreadable or invalid JSON exits with
`2`.

## Risky tool approval audit

`approval_trace_auditor.py` checks that write and irreversible Agent tool calls
have a matching human approval before execution. It also catches execution
after denial, late approvals, duplicate IDs, and references to unknown calls.

```bash
python Core-Agent/approval_trace_auditor.py approval-trace.jsonl
python Core-Agent/approval_trace_auditor.py approval-trace.jsonl --json
python -m unittest Core-Agent/test_approval_trace_auditor.py -v
```

The framework-independent JSONL format supports `tool_requested`,
`approval_decision`, and `tool_executed` events. The command exits with `0`
when the approval chain is safe, `1` for audit findings, and `2` when the file
cannot be read.

## 提交前检查

本目录提供一个仅依赖 Python 标准库的范围检查器，用于确认当前分支、暂存区、
工作区和未跟踪文件中的所有改动都位于 `Core-Agent/` 下：

```bash
python Core-Agent/check_pr_scope.py --base upstream/main
```

如果本地没有名为 `upstream` 的远端，可以省略 `--base`；脚本会依次尝试
`upstream/main`、`origin/main` 和 `main`。

运行单元测试：

```bash
python -m unittest discover -s Core-Agent -p "test_*.py"
```

## Application material checklist

Use the default checklist for common application materials:

```bash
python Core-Agent/material_checklist.py cv transcript
```

The checklist is not fixed. Programs that require a portfolio, writing sample,
GRE, or other materials can provide their own comma-separated lists:

```bash
python Core-Agent/material_checklist.py \
  --required "cv,transcript,portfolio" \
  --prepared "cv,portfolio"
```

Add `--json` when the result needs to be consumed by another tool.
