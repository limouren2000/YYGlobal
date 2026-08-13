import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.mcp import demo_mcp
from app.agent.memory import persist_confirmed_memory
from app.core.config import settings
from app.models.entities import Document, ProgramSource, Task, ToolCall
from app.services.business import (
    create_material_plan,
    create_shortlist,
    create_timeline,
    get_or_create_profile,
    get_program,
    get_requirement,
    search_programs_for_profile,
)
from app.services.requirements import (
    extract_and_save_requirements,
    fetch_official_source,
    verify_program_official,
)

ToolHandler = Callable[[AsyncSession, Dict[str, Any]], Awaitable[Any]]


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: ToolHandler
    mutates_data: bool = False
    approval_required: bool = False

    def as_openai_tool(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "strict": True,
        }

    def as_chat_tool(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def object_schema(properties: Dict[str, Any], required: List[str]) -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def validate_arguments(schema: Dict[str, Any], arguments: Dict[str, Any]) -> None:
    if not isinstance(arguments, dict):
        raise ValueError("工具参数必须是对象")
    properties = schema.get("properties", {})
    missing = [name for name in schema.get("required", []) if name not in arguments]
    if missing:
        raise ValueError(f"缺少必填工具参数：{', '.join(missing)}")
    if schema.get("additionalProperties") is False:
        unknown = sorted(set(arguments) - set(properties))
        if unknown:
            raise ValueError(f"包含未声明工具参数：{', '.join(unknown)}")
    python_types = {"string": str, "array": list, "object": dict, "number": (int, float)}
    for name, value in arguments.items():
        expected = properties.get(name, {}).get("type")
        if expected in python_types and not isinstance(value, python_types[expected]):
            raise ValueError(f"工具参数 {name} 类型应为 {expected}")


async def tool_get_profile(session: AsyncSession, arguments: Dict[str, Any]) -> Any:
    item = await get_or_create_profile(session)
    return {
        "full_name": item.full_name,
        "school": item.current_school,
        "major": item.current_major,
        "gpa": item.gpa,
        "gpa_scale": item.gpa_scale,
        "targets": item.target_fields,
        "countries": item.target_countries,
        "confirmed": item.confirmed,
    }


async def tool_save_profile(session: AsyncSession, arguments: Dict[str, Any]) -> Any:
    item = await get_or_create_profile(session)
    for key, value in arguments.items():
        setattr(item, key, value)
    item.confirmed = True
    await session.commit()
    await session.refresh(item)
    await persist_confirmed_memory(
        session,
        key="applicant_profile",
        value={**arguments, "confirmed": True},
        source_type="user_confirmed",
        source_id=item.id,
    )
    return {"profile_id": item.id, "confirmed": item.confirmed, "status": "saved"}


async def tool_search_programs(session: AsyncSession, arguments: Dict[str, Any]) -> Any:
    items = await search_programs_for_profile(
        session,
        query=arguments.get("query", ""),
        country=arguments.get("country", ""),
        field=arguments.get("field", ""),
    )
    return [
        {
            "id": item.id,
            "university": item.university,
            "name": item.name,
            "country": item.country,
            "field": item.field,
            "tuition": item.tuition,
            "official_url": item.official_url,
            "warning": "未附官网逐字证据的招生字段均为待确认",
        }
        for item in items[:20]
    ]


async def tool_compare_programs(session: AsyncSession, arguments: Dict[str, Any]) -> Any:
    output = []
    for program_id in arguments["program_ids"]:
        program = await get_program(session, program_id)
        if not program:
            continue
        requirement = await get_requirement(session, program_id)
        output.append(
            {
                "id": program.id,
                "university": program.university,
                "program": program.name,
                "tuition": program.tuition,
                "deadline": requirement.deadline if requirement else None,
                "min_gpa": requirement.min_gpa if requirement else None,
                "language": requirement.language if requirement else {},
                "verified": bool(requirement and requirement.verified),
                "official_url": program.official_url,
            }
        )
    return output


async def tool_create_shortlist(session: AsyncSession, arguments: Dict[str, Any]) -> Any:
    item = await create_shortlist(session, arguments["name"], arguments["program_ids"])
    return {"shortlist_id": item.id, "name": item.name, "status": "created"}


async def tool_material_plan(session: AsyncSession, arguments: Dict[str, Any]) -> Any:
    item = await create_material_plan(session, arguments["program_id"])
    return {
        "material_plan_id": item.id,
        "checklist": item.checklist,
        "cv_plan": item.cv_plan,
        "ps_plan": item.ps_plan,
        "gaps": item.gaps,
    }


async def tool_timeline(session: AsyncSession, arguments: Dict[str, Any]) -> Any:
    items = await create_timeline(session, arguments["program_id"])
    return [{"id": item.id, "title": item.title, "due_date": item.due_date} for item in items]


async def tool_mcp_search(session: AsyncSession, arguments: Dict[str, Any]) -> Any:
    return await demo_mcp.call_tool(session, "catalog.search_programs", arguments)


async def tool_parse_document(session: AsyncSession, arguments: Dict[str, Any]) -> Any:
    item = await session.get(Document, arguments["document_id"])
    if not item or item.owner_id != settings.local_owner_id:
        raise ValueError("材料不存在")
    return {
        "document_id": item.id,
        "filename": item.filename,
        "kind": item.kind,
        "parse_status": item.parse_status,
        "candidate_data": item.extracted_data,
        "requires_confirmation": True,
    }


async def tool_fetch_official_source(session: AsyncSession, arguments: Dict[str, Any]) -> Any:
    program = await get_program(session, arguments["program_id"])
    if not program:
        raise ValueError("项目不存在")
    source = await fetch_official_source(session, program)
    await session.commit()
    return {
        "program_id": program.id,
        "source_id": source.id,
        "url": source.url,
        "title": source.title,
        "content_hash": source.content_hash,
        "status": source.status,
    }


async def tool_extract_requirements(session: AsyncSession, arguments: Dict[str, Any]) -> Any:
    program = await get_program(session, arguments["program_id"])
    source = await session.get(ProgramSource, arguments["source_id"])
    if not program or not source or source.program_id != program.id:
        raise ValueError("项目或官网来源不存在")
    return await extract_and_save_requirements(session, program, source)


async def tool_verify_program_official(session: AsyncSession, arguments: Dict[str, Any]) -> Any:
    program = await get_program(session, arguments["program_id"])
    if not program:
        raise ValueError("项目不存在")
    primary, extracted = await verify_program_official(session, program)
    return {
        "program_id": program.id,
        "primary_source_id": primary.id,
        "status": primary.status,
        "official_url": program.official_url,
        "deadline": extracted.get("deadline"),
        "deadlines": extracted.get("deadlines", []),
        "tuition": extracted.get("tuition"),
        "currency": extracted.get("currency", ""),
        "materials": extracted.get("materials", []),
        "language": extracted.get("language", {}),
        "fees": extracted.get("fees", {}),
        "evidence": extracted.get("evidence", []),
        "source_results": extracted.get("source_results", []),
    }


async def tool_update_task(session: AsyncSession, arguments: Dict[str, Any]) -> Any:
    item = await session.get(Task, arguments["task_id"])
    if not item or item.owner_id != settings.local_owner_id:
        raise ValueError("任务不存在")
    for key in ("status", "due_date", "priority", "details"):
        if key in arguments:
            setattr(item, key, arguments[key])
    await session.commit()
    await session.refresh(item)
    return {"task_id": item.id, "status": item.status, "due_date": item.due_date}


class ToolRegistry:
    def __init__(self) -> None:
        self.tools: Dict[str, ToolSpec] = {}
        self._register_defaults()

    def register(self, tool: ToolSpec) -> None:
        self.tools[tool.name] = tool

    def _register_defaults(self) -> None:
        self.register(
            ToolSpec(
                "get_applicant_profile",
                "Read the confirmed applicant profile. Never infer missing facts.",
                object_schema({}, []),
                tool_get_profile,
            )
        )
        self.register(
            ToolSpec(
                "save_applicant_profile",
                "Save only applicant profile fields the user explicitly confirmed in this message.",
                object_schema(
                    {
                        "full_name": {"type": "string"},
                        "current_school": {"type": "string"},
                        "current_major": {"type": "string"},
                        "degree": {"type": "string"},
                        "gpa": {"type": "number"},
                        "gpa_scale": {"type": "number"},
                        "language_scores": {"type": "object"},
                        "target_countries": {"type": "array", "items": {"type": "string"}},
                        "target_fields": {"type": "array", "items": {"type": "string"}},
                        "intake": {"type": "string"},
                        "budget": {"type": "number"},
                        "preferences": {"type": "object"},
                    },
                    [
                        "full_name", "current_school", "current_major", "degree", "gpa",
                        "gpa_scale", "language_scores", "target_countries", "target_fields",
                        "intake", "budget", "preferences",
                    ],
                ),
                tool_save_profile,
                mutates_data=True,
                approval_required=True,
            )
        )
        self.register(
            ToolSpec(
                "search_programs",
                "Search the seeded program catalog. Returned facts may require official verification.",
                object_schema(
                    {
                        "query": {"type": "string"},
                        "country": {"type": "string"},
                        "field": {"type": "string"},
                    },
                    ["query", "country", "field"],
                ),
                tool_search_programs,
            )
        )
        self.register(
            ToolSpec(
                "compare_programs",
                "Compare program requirements and official evidence status.",
                object_schema(
                    {"program_ids": {"type": "array", "items": {"type": "string"}}},
                    ["program_ids"],
                ),
                tool_compare_programs,
            )
        )
        self.register(
            ToolSpec(
                "build_shortlist",
                "Create a shortlist in the YYGlobal workspace.",
                object_schema(
                    {
                        "name": {"type": "string"},
                        "program_ids": {"type": "array", "items": {"type": "string"}},
                    },
                    ["name", "program_ids"],
                ),
                tool_create_shortlist,
                mutates_data=True,
                approval_required=True,
            )
        )
        self.register(
            ToolSpec(
                "build_material_plan",
                "Create grounded CV and PS material plans for one program.",
                object_schema({"program_id": {"type": "string"}}, ["program_id"]),
                tool_material_plan,
                mutates_data=True,
                approval_required=True,
            )
        )
        self.register(
            ToolSpec(
                "build_application_timeline",
                "Create application tasks from one program deadline.",
                object_schema({"program_id": {"type": "string"}}, ["program_id"]),
                tool_timeline,
                mutates_data=True,
                approval_required=True,
            )
        )
        self.register(
            ToolSpec(
                "mcp_catalog_search",
                "Read-only MCP adapter that searches the local program catalog.",
                object_schema({"query": {"type": "string"}}, ["query"]),
                tool_mcp_search,
            )
        )
        self.register(
            ToolSpec(
                "parse_applicant_document",
                "Read already parsed CV, PS, transcript or image candidates. Candidates are never confirmed facts.",
                object_schema({"document_id": {"type": "string"}}, ["document_id"]),
                tool_parse_document,
            )
        )
        self.register(
            ToolSpec(
                "fetch_official_source",
                "Fetch the exact official page configured for a university program and save a traceable source.",
                object_schema({"program_id": {"type": "string"}}, ["program_id"]),
                tool_fetch_official_source,
            )
        )
        self.register(
            ToolSpec(
                "extract_program_requirements",
                "Extract deadlines, tuition, materials and requirements from a fetched official source with verbatim evidence.",
                object_schema(
                    {"program_id": {"type": "string"}, "source_id": {"type": "string"}},
                    ["program_id", "source_id"],
                ),
                tool_extract_requirements,
                mutates_data=True,
            )
        )
        self.register(
            ToolSpec(
                "verify_program_official",
                "Research the program page and relevant same-program official admissions/requirements/tuition pages, then persist evidence-backed fields.",
                object_schema({"program_id": {"type": "string"}}, ["program_id"]),
                tool_verify_program_official,
                mutates_data=True,
            )
        )
        self.register(
            ToolSpec(
                "update_task",
                "Update one application task after explicit user confirmation.",
                object_schema(
                    {
                        "task_id": {"type": "string"}, "status": {"type": "string"},
                        "due_date": {"type": "string"}, "priority": {"type": "string"},
                        "details": {"type": "string"},
                    },
                    ["task_id"],
                ),
                tool_update_task,
                mutates_data=True,
                approval_required=True,
            )
        )

    def allowed(self, names: List[str]) -> List[ToolSpec]:
        return [self.tools[name] for name in names if name in self.tools]

    def resolve_access(
        self,
        names: List[str],
        policy_approval_required: List[str],
        approved_tools: List[str],
    ) -> tuple[List[str], List[str]]:
        """Return tools available now and tools withheld pending explicit approval."""
        approved = set(approved_tools)
        skill_tools = set(names)
        invalid = sorted(approved - skill_tools)
        if invalid:
            raise PermissionError(
                f"获批工具不属于当前 Skill：{', '.join(invalid)}"
            )

        protected = set(policy_approval_required)
        protected.update(
            name
            for name in names
            if name in self.tools and self.tools[name].approval_required
        )
        allowed = [
            name
            for name in names
            if name in self.tools and (name not in protected or name in approved)
        ]
        pending = [
            name
            for name in names
            if name in self.tools and name in protected and name not in approved
        ]
        return allowed, pending

    async def execute(
        self,
        session: AsyncSession,
        run_id: str,
        name: str,
        arguments: Dict[str, Any],
        allowed_names: List[str],
        approved_tools: Optional[List[str]] = None,
    ) -> Any:
        if name not in allowed_names or name not in self.tools:
            raise PermissionError(f"当前 Skill 无权使用工具：{name}")
        tool = self.tools[name]
        if tool.approval_required and name not in set(approved_tools or []):
            raise PermissionError(f"工具 {name} 需要用户明确确认")
        validate_arguments(tool.parameters, arguments)
        started = time.perf_counter()
        trace = ToolCall(run_id=run_id, tool_name=name, arguments=arguments, status="started")
        session.add(trace)
        await session.flush()
        try:
            result = None
            for attempt in range(settings.agent_max_tool_retries + 1):
                try:
                    result = await asyncio.wait_for(
                        tool.handler(session, arguments),
                        timeout=settings.agent_tool_timeout_seconds,
                    )
                    break
                except (TimeoutError, asyncio.TimeoutError) as exc:
                    if attempt >= settings.agent_max_tool_retries:
                        raise TimeoutError(
                            f"工具 {name} 超过 {settings.agent_tool_timeout_seconds} 秒"
                        ) from exc
                except (ConnectionError, httpx.TransportError):
                    if attempt >= settings.agent_max_tool_retries:
                        raise
            trace.result = json.loads(json.dumps(result, ensure_ascii=False, default=str))
            trace.status = "completed"
            return result
        except Exception as exc:
            trace.status = "error"
            trace.error = str(exc)[:1000]
            raise
        finally:
            trace.duration_ms = int((time.perf_counter() - started) * 1000)
            await session.commit()


tool_registry = ToolRegistry()
