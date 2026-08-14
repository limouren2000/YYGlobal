# knowledge_additions 目录导航

> 本目录是 `Core-Agent/` 的**新增补充**，用于演示 **Skill** 与 **Harness** 的理论契约。
> **不修改 `Core-Agent/` 下的任何已有文件**，所有内容仅存在于 `knowledge_additions/` 内。

## 文件清单

```
knowledge_additions/
├── README.md                              # 本文件：导航与阅读顺序
├── SKILL_AND_HARNESS_THEORY.md            # 核心理论：什么是 Skill / Harness、契约、使用教程
├── __init__.py                            # 包标识
├── skills/
│   └── example-skill/
│       └── SKILL.md                       # Skill 示例模版（方法论型：任务计划生成）
└── harness/
    ├── __init__.py                        # 包标识
    ├── example_harness.py                 # Harness 示例模版（CLI + 退出码 + --json）
    └── test_example_harness.py            # 配套 unittest（PASS/FAIL/不可读）
```

## 阅读顺序

1. 先读 [SKILL_AND_HARNESS_THEORY.md](SKILL_AND_HARNESS_THEORY.md) —— 建立 Skill 与 Harness 的概念、契约、协作闭环。
2. 再读 [skills/example-skill/SKILL.md](skills/example-skill/SKILL.md) —— 看 Skill 长什么样、Sanity Checks 怎么写。
3. 最后读 [harness/example_harness.py](harness/example_harness.py) —— 看 Harness 如何把 Skill 的 Sanity Checks 变成可执行的校验。

## 互相印证关系

示例刻意设计成一对闭环：

| Skill 的 Sanity Checks | Harness 的校验规则 |
|------------------------|--------------------|
| 顶层含 `task_id`（非空） | `validate_task_plan` 检查 `task_id` |
| 顶层含 `goal`（非空） | 检查 `goal` |
| `status` ∈ {planned,running,success,error} | 检查 `status` 枚举 |
| `steps` 数组长度 ≥ 1 | 检查 `steps` 非空 |
| `step_id` 非空且不重复 | 检查重复 `step_id` |
| `action` / `tool` 非空 | 检查 `action` / `tool` |
| `order` ≥ 1 的整数 | 检查 `order` 类型与范围 |

> Skill 定义"产出该有什么"，Harness 校验"产出是否真的有"——二者契约一一对应。

## 如何运行示例

> ⚠️ 环境备注：本机 PowerShell 执行策略禁用了脚本加载，自动运行命令可能失败。
> 如遇 `running scripts is disabled` 报错，请先在终端执行：
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force`
> 或直接用 `cmd` 终端运行下面的 `python` 命令。

### 1. 运行 Harness 测试

在 `Core-Agent/` 目录下执行：

```bash
python -m unittest knowledge_additions.harness.test_example_harness -v
```

期望输出：全部用例通过（覆盖退出码 0 / 1 / 2）。

### 2. 用 Harness 校验一个合法计划

```bash
python knowledge_additions/harness/example_harness.py path/to/plan.json
```

合法计划通过时输出 `[PASS]`，退出码 `0`。

### 3. 用 --json 输出机器可读结果

```bash
python knowledge_additions/harness/example_harness.py path/to/plan.json --json
```

### 4. 用内联 JSON 字符串校验

```bash
python knowledge_additions/harness/example_harness.py --json-string "{\"task_id\":\"p1\",\"goal\":\"demo\",\"status\":\"planned\",\"steps\":[{\"step_id\":\"s1\",\"action\":\"x\",\"tool\":\"y\",\"order\":1}]}"
```

## 与 Core-Agent 现有资产的衔接

| 本目录产物 | 呼应的现有资产 |
|-----------|---------------|
| skill 示例的 frontmatter + 章节 | `Core-Agent/my_skills/*/SKILL.md` |
| harness 的 argparse + 退出码 0/1/2 | `Core-Agent/agent_trace_validator.py` |
| harness 的 unittest 风格 | `Core-Agent/test_*.py` |
| skill 的任务计划概念 | `Core-Agent/AGENT_TASK_TEMPLATE.md` |
| harness 的契约校验思路 | `Core-Agent/audit_skill_contracts.py`（轻量教学版） |

> 本目录是教学/模版性质，不与现有工具产生运行时依赖。
