# Core-Agent Toolkit

`Core-Agent` contains small, dependency-light tools for validating agent
contracts, tool calls, traces, evidence, approvals, and pull-request scope.
The scripts are intentionally independent of the main application so they can
be used during development or in CI.

## Quick start

Run the complete unit-test suite with:

```bash
python -m unittest discover -s Core-Agent -p "test_*.py" -v
```

Most tools use only the Python standard library. `tool_arguments_validator.py`
uses the `jsonschema` dependency declared by the API environment.

## Common checks

Check that a branch changes files only under `Core-Agent/`:

```bash
python Core-Agent/check_pr_scope.py --base origin/main
```

Audit skill contracts before importing the API skills:

```bash
python Core-Agent/audit_skill_contracts.py
```

Validate model-generated tool arguments against a JSON Schema:

```bash
python Core-Agent/tool_arguments_validator.py \
  --schema path/to/tool.schema.json \
  --arguments path/to/arguments.json
```

Validate JSONL agent traces and approval chains:

```bash
python Core-Agent/agent_trace_validator.py path/to/trace.jsonl
python Core-Agent/approval_trace_auditor.py approval-trace.jsonl
```

Audit evidence bundles and guardrail coverage:

```bash
python Core-Agent/evidence_bundle_auditor.py evidence.json
python Core-Agent/guardrail_coverage_auditor.py
```

Use `--json` on supported commands when results need to be consumed by CI or
another automation step. Exit code `0` indicates a passing check, while `1`
indicates findings and `2` indicates invalid input or an unreadable repository.

For the Chinese documentation, see [`README_zh.md`](README_zh.md).
