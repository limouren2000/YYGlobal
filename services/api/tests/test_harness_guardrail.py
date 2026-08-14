import json

import app.agent.harness as harness_module
from app.agent.harness import AgentHarness
from app.core.database import SessionLocal


async def run_harness(monkeypatch, structured_output):
    events = []

    async def fake_run(**kwargs):
        return json.dumps(structured_output, ensure_ascii=False), {"mode": "fake", "total_tokens": 0}

    async def emit(event, data):
        events.append((event, data))

    monkeypatch.setattr(harness_module.provider, "run", fake_run)
    async with SessionLocal() as session:
        run = await AgentHarness().run(session, "请比较项目", emit=emit)
        await session.refresh(run)
    return run, events


async def test_safe_structured_output_is_preserved_and_emitted(client, monkeypatch):
    safe_output = {
        "dimensions": ["录取要求"],
        "programs": [],
        "risks": [],
        "summary": "请根据官网要求比较项目。",
    }

    run, events = await run_harness(monkeypatch, safe_output)

    completed = next(data for event, data in events if event == "message.completed")
    assert run.stop_reason == "success"
    assert run.final_output == safe_output["summary"]
    assert run.structured_output == safe_output
    assert completed["structured_output"] == safe_output


async def test_output_guardrail_contains_blocked_structured_output(client, monkeypatch):
    blocked_output = {
        "dimensions": ["录取要求"],
        "programs": [],
        "risks": [],
        "summary": "保证录取",
    }

    run, events = await run_harness(monkeypatch, blocked_output)

    completed = next(data for event, data in events if event == "message.completed")
    assert any(event == "guardrail.triggered" for event, _ in events)
    assert run.stop_reason == "output_guardrail"
    assert run.final_output == "模型输出未通过安全检查，请换一种方式描述任务。"
    assert run.structured_output == {}
    assert completed["content"] == run.final_output
    assert completed["structured_output"] == {}
