助力每一个梦想，PR 请提交到这里。

## Skill 契约审计

`audit_skill_contracts.py` 会在 API 导入 `services/api/app/skills` 下的每个包之前，对其进行校验。审计会检查必需文件、frontmatter 元数据、JSON Schema 结构、评测用例、已注册的工具名称以及审批策略的一致性。

```bash
python Core-Agent/audit_skill_contracts.py
python Core-Agent/audit_skill_contracts.py --json
python -m unittest discover -s Core-Agent -p "test_*.py" -v
```

当所有契约通过时命令以 `0` 退出，发现契约问题时以 `1` 退出，无法检查仓库时以 `2` 退出。JSON 输出适合用于 CI 或其他自动化流程。

## 工具参数校验

`tool_arguments_validator.py` 使用 `jsonschema` 提供的完整 JSON Schema Draft 2020-12 实现，校验模型生成的工具参数。它会检查嵌套对象和数组、枚举、数值/字符串限制、必填字段以及 additional-property 规则，而不是依赖浅层的顶层类型检查。

在 API 开发环境中运行（`jsonschema` 已是其声明依赖）：

```bash
services/api/.venv/bin/python Core-Agent/tool_arguments_validator.py \
  --schema path/to/tool.schema.json \
  --arguments path/to/arguments.json
```

在自动化流程中使用内联参数和 JSON 输出：

```bash
services/api/.venv/bin/python Core-Agent/tool_arguments_validator.py \
  --schema path/to/tool.schema.json \
  --arguments-json '{"program_ids":["program-1"]}' \
  --json
```

退出码：`0` 表示参数有效，`1` 表示违反 schema，`2` 表示 schema 无效或 JSON 输入不可读。Python 调用方可以导入 `validate_tool_arguments` 获取结构化问题，或使用 `require_valid_tool_arguments` 作为基于异常的拦截门。

## Agent trace 校验

`agent_trace_validator.py` 检查一种紧凑、与框架无关的 JSONL 事件契约。它会校验每个 trace 中的必填字段、状态、时长、步骤关系以及事件顺序。支持常规 UTF-8 以及带字节序标记（BOM）的 UTF-8 文件。

```bash
python Core-Agent/agent_trace_validator.py path/to/trace.jsonl
python -m unittest Core-Agent/test_agent_trace_validator.py -v
```

命令以 `0` 退出表示 trace 有效，`1` 表示存在校验问题，`2` 表示无法读取输入。

## 高风险工具审批审计

`approval_trace_auditor.py` 用于检查写操作和不可逆 Agent 工具调用是否在执行前获得了匹配的人工审批。它也会发现拒绝后执行、事后审批、重复 ID，以及对未知调用的引用。

```bash
python Core-Agent/approval_trace_auditor.py approval-trace.jsonl
python Core-Agent/approval_trace_auditor.py approval-trace.jsonl --json
python -m unittest Core-Agent/test_approval_trace_auditor.py -v
```

这个与框架无关的 JSONL 格式支持 `tool_requested`、`approval_decision` 和 `tool_executed` 事件。审批链安全时命令以 `0` 退出，发现审计问题时以 `1` 退出，文件无法读取时以 `2` 退出。

## 提交前检查

本目录提供一个仅依赖 Python 标准库的范围检查器，用于确认当前分支、暂存区、工作区和未跟踪文件中的所有改动都位于 `Core-Agent/` 下：

```bash
python Core-Agent/check_pr_scope.py --base upstream/main
```

如果本地没有名为 `upstream` 的远端，可以省略 `--base`；脚本会依次尝试 `upstream/main`、`origin/main` 和 `main`。

运行单元测试：

```bash
python -m unittest discover -s Core-Agent -p "test_*.py"
```

## 申请材料清单

使用默认清单检查常见的申请材料：

```bash
python Core-Agent/material_checklist.py cv transcript
```

清单并非固定不变。需要作品集、写作样本、GRE 或其他材料的项目，可以提供自己的逗号分隔列表：

```bash
python Core-Agent/material_checklist.py \
  --required "cv,transcript,portfolio" \
  --prepared "cv,portfolio"
```

当结果需要被其他工具消费时，可添加 `--json`。
