import json
from types import SimpleNamespace

import pytest

from app.agent.provider import DashScopeChatProvider
from app.agent.skills import local_skill_output, parse_skill_output, skill_registry
from app.core.database import SessionLocal
from app.schemas.api import ProfileUpdate
from app.services.business import search_programs_for_profile, update_profile
from app.services.requirements import (
    extract_requirement_candidates,
    merge_ai_extraction,
    merge_source_extractions,
)


async def test_catalog_is_driven_by_profile_target_field():
    async with SessionLocal() as session:
        await update_profile(
            session,
            ProfileUpdate(
                current_major="Business Administration",
                target_countries=["United States"],
                target_fields=["商科"],
                confirmed=True,
            ),
        )
        business = await search_programs_for_profile(session)
        assert business
        assert {item.field for item in business} <= {"Business Analytics", "Finance", "Accounting"}
        assert all("master" in item.name.lower() for item in business)

        await update_profile(
            session,
            ProfileUpdate(
                current_major="Computer Science",
                target_countries=["United States"],
                target_fields=["计算机"],
                confirmed=True,
            ),
        )
        computer = await search_programs_for_profile(session)
        assert len(computer) >= 20
        assert {item.field for item in computer} == {"Computer Science"}
        assert all("cs" in item.official_url.lower() or "computer" in item.official_url.lower() for item in computer)

        for target, expected in [
            ("商业分析", {"Business Analytics"}),
            ("金融", {"Finance"}),
            ("会计", {"Accounting"}),
            ("公共政策", {"Public Policy"}),
        ]:
            await update_profile(
                session,
                ProfileUpdate(
                    target_countries=["United States"], target_fields=[target], confirmed=True
                ),
            )
            matched = await search_programs_for_profile(session)
            assert matched, target
            assert {item.field for item in matched} == expected
            assert all(item.official_url.startswith("https://") for item in matched)


def test_requirement_extraction_covers_deadline_tuition_materials_and_verbatim_evidence():
    text = """
    Application Deadline: January 5, 2027
    Tuition and fees: $76,700 for the academic year.
    Application fee: $100.
    Minimum GPA 3.20 is expected.
    TOEFL minimum score 100. IELTS minimum score 7.0.
    Submit a resume, statement of purpose, official transcript, and three recommendation letters.
    Required quantitative preparation includes calculus and statistics.
    """
    extracted = extract_requirement_candidates(text)
    assert extracted["deadline"] == "2027-01-05"
    assert extracted["tuition"] == 76700
    assert extracted["fees"]["application_fee"] == 100
    assert extracted["min_gpa"] == 3.2
    assert extracted["language"] == {"TOEFL": 100.0, "IELTS": 7.0}
    assert {"CV / Resume", "Statement of Purpose / Essays", "Transcripts", "Recommendations"} <= set(extracted["materials"])
    assert extracted["evidence"]
    assert all(item["quote"] in text for item in extracted["evidence"])


def test_requirement_extraction_keeps_all_rounds_and_rejects_graduation_gpa():
    text = """
    Application Round 1 deadline: October 1, 2026
    Application Round 2 deadline: January 5, 2027
    Students must maintain at least a 3.0 GPA to graduate.
    """
    extracted = extract_requirement_candidates(text)
    assert [item["date"] for item in extracted["deadlines"]] == [
        "2026-10-01", "2027-01-05"
    ]
    assert extracted["min_gpa"] is None
    assert not any(item["field"] == "min_gpa" for item in extracted["evidence"])

    table_text = """
    Application Deadline
    The committee reviews applications before the dates listed below.
    Deadline
    Decision date
    January 5, 2027
    March 2027
    """
    table = extract_requirement_candidates(table_text)
    assert table["deadline"] == "2027-01-05"
    assert table["deadlines"][0]["raw"] == "January 5, 2027"


def test_ai_requirement_evidence_must_exist_verbatim():
    text = "Application Deadline: January 5, 2027"
    rules = extract_requirement_candidates(text)
    ai = {
        "tuition": 99999,
        "materials": ["CV"],
        "evidence": [
            {"field": "tuition", "quote": "Tuition is $99,999", "value": 99999, "confidence": 0.9},
            {"field": "materials", "quote": "Application Deadline: January 5, 2027", "value": "CV", "confidence": 0.5},
        ],
    }
    merged = merge_ai_extraction(rules, ai, text)
    assert merged.get("tuition") is None
    assert merged["materials"] == ["CV"]
    assert all(item["quote"] in text for item in merged["evidence"])


def test_merged_requirements_do_not_promote_past_deadlines():
    source = SimpleNamespace(id="source-1", url="https://example.edu/program")
    merged = merge_source_extractions(
        [
            (
                source,
                {
                    "deadline": "2024-02-01",
                    "deadline_raw": "February 1",
                    "deadlines": [
                        {"date": "2024-02-01", "raw": "February 1", "round": ""}
                    ],
                    "evidence": [
                        {
                            "field": "deadline",
                            "quote": "The application deadline is February 1.",
                            "confidence": 0.9,
                        }
                    ],
                },
            )
        ]
    )
    assert merged["deadline"] is None
    assert merged["deadlines"] == []
    assert merged["evidence"][0]["quote"] == "The application deadline is February 1."


def test_all_seven_skill_outputs_enforce_json_schema():
    assert len(skill_registry.list()) == 7
    for skill in skill_registry.list():
        assert skill_registry.validate_output(skill, local_skill_output(skill, {}))
        with pytest.raises(ValueError):
            parse_skill_output(skill, "普通自然语言不是结构化输出")
        with pytest.raises(ValueError):
            skill_registry.validate_input(skill, {"unexpected": True})


class CorrectingCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            content = "不符合 Schema"
        else:
            content = json.dumps(
                {
                    "programs": [], "sources": [], "unverified": ["待确认"],
                    "summary": "已完成结构化纠错。",
                },
                ensure_ascii=False,
            )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(role="assistant", content=content, tool_calls=None))],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )


async def test_dashscope_repairs_invalid_skill_output_once():
    fake = CorrectingCompletions()
    provider = DashScopeChatProvider()
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=fake))
    skill = skill_registry.get("program-research")
    async with SessionLocal() as session:
        output, _ = await provider.run(
            session, "schema-repair", "搜索项目", {}, skill,
            SimpleNamespace(allowed=lambda names: []),
        )
    assert "没有从项目目录" in json.loads(output)["summary"]
    assert len(fake.calls) == 2
    assert "输出校验失败" in fake.calls[1]["messages"][-1]["content"]
