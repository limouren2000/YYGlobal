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

## Agent run budget audit

`agent_run_budget_auditor.py` checks the real JSON shape returned by
`GET /api/agent-runs/{run_id}/trace`. It verifies that both planned and
persisted steps stay within the Agent step budget, counts every tool-call record
against the call budget, checks per-call timeouts, and reports malformed
durations or duplicate step positions. It uses only the Python standard library.

```bash
curl -o trace.json http://localhost:8000/api/agent-runs/RUN_ID/trace
python Core-Agent/agent_run_budget_auditor.py trace.json
python Core-Agent/agent_run_budget_auditor.py trace.json \
  --max-steps 8 \
  --max-tool-calls 12 \
  --tool-timeout-seconds 30 \
  --json
python -m unittest Core-Agent/test_agent_run_budget_auditor.py -v
```

The defaults match YYGlobal's current Agent settings. Exit codes are `0` when
the run is within budget, `1` for budget or trace-integrity findings, and `2`
when the input cannot be read or parsed.
## Agent handoff validation

`agent_handoff_validator.py` validates a compact JSON handoff before one Agent
passes work to another. It requires distinct sender and receiver names, a
summary, at least one actionable next step, and lists for completed work,
evidence, and risks. A blocked handoff must state its blocker in `risks`.

```bash
python Core-Agent/agent_handoff_validator.py handoff.json
python Core-Agent/agent_handoff_validator.py handoff.json --json
python -m unittest Core-Agent/test_agent_handoff_validator.py -v
```

Example:

```json
{
  "handoff_id": "research-to-writer-001",
  "from_agent": "research-agent",
  "to_agent": "writing-agent",
  "summary": "Official requirements have been verified.",
  "completed": ["Checked the program deadline."],
  "next_steps": ["Draft an application timeline."],
  "evidence": ["https://example.edu/admissions"],
  "risks": [],
  "status": "ready"
}
```

The command exits with `0` for a valid handoff, `1` for contract violations,
and `2` for unreadable or invalid JSON.

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

## Guardrail coverage audit

`guardrail_coverage_auditor.py` cross-references two independently maintained
approval layers: the global `ToolSpec.approval_required` flag in
`services/api/app/agent/tools.py`, and each Skill's own `approval_required`
list in `tool-policy.yaml`. Because these live in different files, a
data-mutating tool (`mutates_data=True`) can drift out of sync and become
reachable by a Skill without any human-approval gate on either layer. The
auditor parses both sources with `ast` / `yaml`, without importing the
FastAPI application, and reports every Skill/tool pair with this gap.

```bash
python Core-Agent/guardrail_coverage_auditor.py
python Core-Agent/guardrail_coverage_auditor.py --json
python -m unittest Core-Agent/test_guardrail_coverage_auditor.py -v
```

Running it against the current repository surfaces real, pre-existing gaps:
`extract_program_requirements` and `verify_program_official` both mutate data
but are not listed in the `approval_required` section of every Skill that can
call them (`program-research`, `application-timeline`, `program-compare`,
`shortlist-builder`). Maintainers can either add these tools to the relevant
Skill's `approval_required` list, set `approval_required=True` on the
`ToolSpec`, or record an intentional exception:

```bash
python Core-Agent/guardrail_coverage_auditor.py \
  --allow program-research:verify_program_official \
  --allow application-timeline:extract_program_requirements
```

Repeatable exemptions can also be kept in a text file (one `skill:tool` or
bare `tool` per line, `#` starts a comment) and passed with
`--allowlist-file`. The command exits with `0` when every mutating tool is
gated, `1` when gaps are found, and `2` when the repository cannot be
inspected.

## 提交前检查

本目录提供一个仅依赖 Python 标准库的范围检查器，用于确认当前分支、暂存区、
工作区和未跟踪文件中的所有改动都位于 `Core-Agent/` 下：

```bash
python Core-Agent/check_pr_scope.py --base upstream/main
```

如果本地没有名为 `upstream` 的远端，可以省略 `--base`；脚本会依次尝试
`upstream/main`、`origin/main` 和 `main`。

面向 Core-Agent 的 PR 建议在提交前先运行这个范围检查，避免把根目录、
Web 应用或 API 服务中的无关改动一起带入评审。

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

## Program code validation

`program_code_validator.py` 校验留学申请场景中的项目编号格式，只使用 Python
标准库。项目编号由字母、数字和连字符组成（如 `USC-MSCS`），末尾可携带入学
学期后缀（如 `-2026FALL` / `-2027SPRING`），用于研究项目、创建选校清单等
流程前的统一规范化。

```bash
python Core-Agent/program_code_validator.py "USC-MSCS-2026FALL"
python Core-Agent/program_code_validator.py "us-mscs" --json
```

命令以 `0` 表示编号有效、`1` 表示无效。`--json` 输出结构化结果，包含规范化
后的编号与识别出的入学学期，便于其他工具消费。
## Personal statement quality check

`ps_quality_checker.py` turns the three acceptance criteria the `ps-planner`
skill declares in its own prompt — stay on-topic, do not misuse the school
name, and only cite traceable material — into deterministic checks. It flags
leftover placeholders, word counts outside the configured limits, prompt
requirements that appear unaddressed, cited experiences that are not among the
confirmed set, and school names that differ from the target program.

The input is a JSON bundle mirroring the `ps-planner` output plus the target
program and the applicant's confirmed experiences:

```bash
python Core-Agent/ps_quality_checker.py ps-bundle.json
python Core-Agent/ps_quality_checker.py ps-bundle.json --json
python -m unittest Core-Agent/test_ps_quality_checker.py -v
```

The command exits with `0` when no errors are found, `1` when errors are found,
and `2` when the input cannot be read or parsed. Warnings do not fail the check.
