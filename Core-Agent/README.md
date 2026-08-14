助力每一个梦想，PR 请提交到这里。

## 工具清单

- `material_normalizer.py` — 把官网抽取的材料要求归一成标准类别，并映射到资产库槽位。
  解决「推荐信被抽取成整句原文」和「English proficiency / GRE / GMAT 无法匹配资产库」
  两类问题。用法：

  ```bash
  python Core-Agent/material_normalizer.py --json '["We request 3 letters, at least two of which are from faculty or recent employers."]'
  ```

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
