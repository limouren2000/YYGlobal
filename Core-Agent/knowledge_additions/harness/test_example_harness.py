"""example_harness.py 的单元测试。

覆盖三类用例，对应退出码 0 / 1 / 2：
  - PASS：合法计划 -> 退出码 0
  - FAIL：契约不满足 -> 退出码 1
  - ERROR：输入不可读或 JSON 无效 -> 退出码 2

运行：
    python -m unittest knowledge_additions.harness.test_example_harness -v
"""

from __future__ import annotations
# import sys
# sys.path.append("..")
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from knowledge_additions.harness.example_harness import main, validate_task_plan


def _valid_plan() -> dict:
    """返回一个合法的任务计划，供各测试按需改动。"""
    return {
        "task_id": "plan-001",
        "goal": "查某公司舆情并写摘要",
        "status": "planned",
        "steps": [
            {"step_id": "s1", "action": "web_search", "tool": "search_api", "order": 1},
            {"step_id": "s2", "action": "summarize", "tool": "llm", "order": 2},
        ],
    }


class ValidateTaskPlanTests(unittest.TestCase):
    """直接测试纯函数 validate_task_plan。"""

    def test_valid_plan_has_no_issues(self) -> None:
        issues, warnings = validate_task_plan(_valid_plan())
        self.assertEqual(issues, [])
        self.assertEqual(warnings, [])

    def test_top_level_not_object(self) -> None:
        issues, _ = validate_task_plan([1, 2, 3])
        self.assertTrue(any("顶层" in i for i in issues))

    def test_missing_task_id(self) -> None:
        plan = _valid_plan()
        del plan["task_id"]
        issues, _ = validate_task_plan(plan)
        self.assertTrue(any("task_id" in i for i in issues))

    def test_empty_task_id(self) -> None:
        plan = _valid_plan()
        plan["task_id"] = "   "
        issues, _ = validate_task_plan(plan)
        self.assertTrue(any("task_id" in i for i in issues))

    def test_invalid_status(self) -> None:
        plan = _valid_plan()
        plan["status"] = "done"
        issues, _ = validate_task_plan(plan)
        self.assertTrue(any("status" in i for i in issues))

    def test_empty_steps(self) -> None:
        plan = _valid_plan()
        plan["steps"] = []
        issues, _ = validate_task_plan(plan)
        self.assertTrue(any("不能为空" in i for i in issues))

    def test_duplicate_step_id(self) -> None:
        plan = _valid_plan()
        plan["steps"][1]["step_id"] = "s1"
        issues, _ = validate_task_plan(plan)
        self.assertTrue(any("重复" in i for i in issues))

    def test_order_must_be_positive_int(self) -> None:
        plan = _valid_plan()
        plan["steps"][0]["order"] = 0
        issues, _ = validate_task_plan(plan)
        self.assertTrue(any("order" in i for i in issues))

    def test_order_bool_is_rejected(self) -> None:
        # bool 是 int 的子类，必须被拒绝
        plan = _valid_plan()
        plan["steps"][0]["order"] = True
        issues, _ = validate_task_plan(plan)
        self.assertTrue(any("order" in i for i in issues))

    def test_discontinuous_order_only_warns(self) -> None:
        plan = _valid_plan()
        plan["steps"][0]["order"] = 5  # 跳号，但不影响通过
        issues, warnings = validate_task_plan(plan)
        self.assertEqual(issues, [])
        self.assertTrue(any("order" in w for w in warnings))


class CliExitCodeTests(unittest.TestCase):
    """测试 CLI 退出码 0 / 1 / 2。"""

    def _run(self, argv: list[str]) -> tuple[int, str, str]:
        """运行 main(argv)，返回 (return_code, stdout, stderr)。"""
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_pass_returns_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps(_valid_plan()), encoding="utf-8")
            code, out, _ = self._run([str(path)])
        self.assertEqual(code, 0)
        self.assertIn("[PASS]", out)

    def test_fail_returns_one(self) -> None:
        plan = _valid_plan()
        del plan["task_id"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            code, out, _ = self._run([str(path)])
        self.assertEqual(code, 1)
        self.assertIn("[FAIL]", out)

    def test_unreadable_file_returns_two(self) -> None:
        code, _, err = self._run(["/no/such/file/exists.json"])
        self.assertEqual(code, 2)
        self.assertIn("[ERROR]", err)

    def test_invalid_json_returns_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text("{not valid json", encoding="utf-8")
            code, _, _ = self._run([str(path)])
        self.assertEqual(code, 2)

    def test_json_string_input(self) -> None:
        code, out, _ = self._run(["--json-string", json.dumps(_valid_plan()), "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertTrue(payload["passed"])

    def test_json_output_format(self) -> None:
        plan = _valid_plan()
        del plan["status"]
        code, out, _ = self._run(["--json-string", json.dumps(plan), "--json"])
        self.assertEqual(code, 1)
        payload = json.loads(out)
        self.assertFalse(payload["passed"])
        self.assertGreater(payload["issue_count"], 0)

    def test_no_input_errors(self) -> None:
        # 既没给文件也没给 --json-string，argparse 应报错退出
        with self.assertRaises(SystemExit) as ctx:
            self._run([])
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
