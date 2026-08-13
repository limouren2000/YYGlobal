import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.guardrails import check_user_input, verify_output
from app.agent.harness import harness
from app.agent.mcp import demo_mcp
from app.agent.memory import persist_confirmed_memory
from app.agent.provider import provider
from app.agent.skills import skill_registry
from app.agent.tools import tool_registry
from app.core.config import settings
from app.core.database import get_session
from app.models.entities import (
    AgentRun,
    AgentStep,
    ApplicantProfile,
    Application,
    ApplicationPackage,
    Conversation,
    Document,
    EvidenceChunk,
    Experience,
    MaterialArtifact,
    MaterialDraft,
    MaterialPlan,
    MCPConnection,
    Memory,
    Message,
    Program,
    ProgramSource,
    Shortlist,
    ShortlistItem,
    Task,
    ToolCall,
)
from app.schemas.api import (
    AgentRunResponse,
    ApplicationCreate,
    ApplicationPackageResponse,
    ApplicationResponse,
    ApplicationUpdate,
    BatchVerifyResponse,
    ChatRequest,
    DocumentConfirmRequest,
    DocumentResponse,
    EvidenceResponse,
    HealthResponse,
    MaterialArtifactCreate,
    MaterialArtifactResponse,
    MaterialArtifactUpdate,
    MaterialDraftGenerate,
    MaterialDraftResponse,
    MaterialDraftUpdate,
    MaterialPlanCreate,
    MaterialPlanResponse,
    MaterialPreflightRequest,
    MaterialPreflightResponse,
    MCPServerResponse,
    MemoryResponse,
    PackageMaterialUpdate,
    ProfileResponse,
    ProfileUpdate,
    ProgramResponse,
    ProgramVerifyResponse,
    RequirementResponse,
    ShortlistCreate,
    ShortlistItemResponse,
    ShortlistResponse,
    SkillResponse,
    SourceResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
    TimelineCreate,
    TraceResponse,
)
from app.services.business import (
    create_material_plan,
    create_shortlist,
    create_task,
    create_timeline,
    get_or_create_application_package,
    get_program,
    get_requirement,
    profile_with_experiences,
    search_programs_for_profile,
    update_profile,
)
from app.services.documents import (
    SUPPORTED_MIME_TYPES,
    extract_text,
    infer_document_data,
    sha256_bytes,
)
from app.services.material_exports import (
    content_disposition,
    docx_export,
    export_filename,
    pdf_export,
)
from app.services.requirements import verify_program_official
from app.services.web import UnsafeUrlError

router = APIRouter()


def profile_response(profile: Any, experiences: List[Any]) -> ProfileResponse:
    data = ProfileResponse.model_validate(profile).model_dump()
    data["experiences"] = [
        {
            "id": item.id,
            "kind": item.kind,
            "title": item.title,
            "organization": item.organization,
            "start_date": item.start_date,
            "end_date": item.end_date,
            "description": item.description,
            "tags": item.tags,
            "confirmed": item.confirmed,
        }
        for item in experiences
    ]
    return ProfileResponse(**data)


async def serialize_program(session: AsyncSession, program: Program) -> ProgramResponse:
    requirement = await get_requirement(session, program.id)
    sources = list(
        (
            await session.scalars(
                select(ProgramSource).where(ProgramSource.program_id == program.id)
            )
        ).all()
    )
    evidence = list(
        (
            await session.scalars(
                select(EvidenceChunk).where(EvidenceChunk.program_id == program.id)
            )
        ).all()
    )
    payload = ProgramResponse.model_validate(program).model_dump()
    payload["requirement"] = (
        RequirementResponse.model_validate(requirement) if requirement else None
    )
    payload["sources"] = [SourceResponse.model_validate(item) for item in sources]
    payload["evidence"] = [EvidenceResponse.model_validate(item) for item in evidence]
    return ProgramResponse(**payload)


@router.get("/health", response_model=HealthResponse)
async def health(session: AsyncSession = Depends(get_session)) -> HealthResponse:
    await session.scalar(select(1))
    return HealthResponse(
        status="ok",
        database="ok",
        llm_mode=provider.mode,
        version="0.1.0",
    )


@router.get("/profile", response_model=ProfileResponse)
async def get_profile_route(session: AsyncSession = Depends(get_session)) -> ProfileResponse:
    profile, experiences = await profile_with_experiences(session)
    return profile_response(profile, experiences)


@router.put("/profile", response_model=ProfileResponse)
async def put_profile_route(
    payload: ProfileUpdate, session: AsyncSession = Depends(get_session)
) -> ProfileResponse:
    profile, experiences = await update_profile(session, payload)
    if payload.confirmed:
        await persist_confirmed_memory(
            session,
            key="applicant_profile",
            value=payload.model_dump(exclude={"experiences"}),
            source_type="user_confirmed",
            source_id=profile.id,
        )
    return profile_response(profile, experiences)


@router.get("/profile/export")
async def export_profile(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    profile, experiences = await profile_with_experiences(session)
    memories = list(
        (
            await session.scalars(
                select(Memory).where(
                    Memory.owner_id == settings.local_owner_id,
                    Memory.active.is_(True),
                )
            )
        ).all()
    )
    payload = {
        "export_version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile_response(profile, experiences).model_dump(mode="json"),
        "memories": [MemoryResponse.model_validate(item).model_dump(mode="json") for item in memories],
    }
    return JSONResponse(
        payload,
        headers={"Content-Disposition": 'attachment; filename="yyglobal-profile.json"'},
    )


@router.delete("/profile", status_code=204)
async def clear_profile(
    confirm: str = Query(""), session: AsyncSession = Depends(get_session)
) -> None:
    if confirm != "DELETE_MY_P0_DATA":
        raise HTTPException(400, "必须提供 confirm=DELETE_MY_P0_DATA")

    document_paths = list(
        (
            await session.scalars(
                select(Document.path).where(Document.owner_id == settings.local_owner_id)
            )
        ).all()
    )
    run_ids = list(
        (
            await session.scalars(
                select(AgentRun.id).where(AgentRun.owner_id == settings.local_owner_id)
            )
        ).all()
    )
    shortlist_ids = list(
        (
            await session.scalars(
                select(Shortlist.id).where(Shortlist.owner_id == settings.local_owner_id)
            )
        ).all()
    )
    conversation_ids = list(
        (
            await session.scalars(
                select(Conversation.id).where(Conversation.owner_id == settings.local_owner_id)
            )
        ).all()
    )
    if run_ids:
        await session.execute(delete(ToolCall).where(ToolCall.run_id.in_(run_ids)))
        await session.execute(delete(AgentStep).where(AgentStep.run_id.in_(run_ids)))
    if shortlist_ids:
        await session.execute(
            delete(ShortlistItem).where(ShortlistItem.shortlist_id.in_(shortlist_ids))
        )
    if conversation_ids:
        await session.execute(
            delete(Message).where(Message.conversation_id.in_(conversation_ids))
        )
    for model in (
        Application,
        ApplicationPackage,
        MaterialArtifact,
        MaterialDraft,
        MaterialPlan,
        Task,
        Memory,
        AgentRun,
        Conversation,
        Shortlist,
        Experience,
        Document,
        ApplicantProfile,
    ):
        await session.execute(delete(model).where(model.owner_id == settings.local_owner_id))
    await session.commit()
    for value in document_paths:
        path = Path(value)
        if path.is_file() and settings.upload_dir in path.parents:
            path.unlink(missing_ok=True)


@router.post("/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    kind: str = Form("other"),
    session: AsyncSession = Depends(get_session),
) -> DocumentResponse:
    mime_type = file.content_type or "application/octet-stream"
    if mime_type not in SUPPORTED_MIME_TYPES:
        raise HTTPException(415, "仅支持 PDF、DOCX、TXT、Markdown、PNG 和 JPEG")
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"文件不能超过 {settings.max_upload_mb}MB")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "upload").suffix.lower()[:10]
    path = settings.upload_dir / f"{uuid4().hex}{suffix}"
    path.write_bytes(content)
    text, status = extract_text(path, mime_type)
    extracted_data = infer_document_data(text, kind)
    if provider.available:
        try:
            extracted_data = await provider.extract_document(path, mime_type, kind, text)
            status = (
                "parsed_multimodal"
                if mime_type.startswith("image/") or not text.strip()
                else "parsed_ai"
            )
        except Exception as exc:
            extracted_data["ai_extraction_error"] = str(exc)[:300]
            if not text.strip():
                status = "needs_multimodal_review"
    item = Document(
        owner_id=settings.local_owner_id,
        filename=Path(file.filename or "upload").name[:255],
        mime_type=mime_type,
        kind=kind,
        path=str(path),
        sha256=sha256_bytes(content),
        parse_status=status,
        extracted_text=text[:200_000],
        extracted_data=extracted_data,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return DocumentResponse.model_validate(item)


@router.post("/documents/{document_id}/confirm", response_model=ProfileResponse)
async def confirm_document_candidates(
    document_id: str,
    payload: DocumentConfirmRequest,
    session: AsyncSession = Depends(get_session),
) -> ProfileResponse:
    document = await session.get(Document, document_id)
    if not document or document.owner_id != settings.local_owner_id:
        raise HTTPException(404, "材料不存在")
    allowed = {"gpa", "gpa_scale", "language_scores"}
    unknown = set(payload.accepted_fields) - allowed
    if unknown:
        raise HTTPException(400, f"不支持自动写入的候选字段：{', '.join(sorted(unknown))}")
    profile, experiences = await profile_with_experiences(session)
    candidates = document.extracted_data or {}
    by_field = {
        item.get("field"): item for item in candidates.get("candidate_facts", [])
        if isinstance(item, dict) and item.get("field")
    }
    accepted: Dict[str, Any] = {}
    if "gpa" in payload.accepted_fields and "gpa" in by_field:
        raw = by_field["gpa"].get("value")
        match = re.search(r"\d+(?:\.\d+)?", str(raw))
        if match:
            profile.gpa = float(match.group())
            accepted["gpa"] = profile.gpa
    if "gpa_scale" in payload.accepted_fields and "gpa" in by_field:
        raw = f"{by_field['gpa'].get('value', '')}/{by_field['gpa'].get('scale', '')}"
        numbers = re.findall(r"\d+(?:\.\d+)?", raw)
        if len(numbers) >= 2:
            profile.gpa_scale = float(numbers[1])
            accepted["gpa_scale"] = profile.gpa_scale
    if "language_scores" in payload.accepted_fields and candidates.get("language_scores"):
        profile.language_scores = candidates["language_scores"]
        accepted["language_scores"] = profile.language_scores
    if not accepted:
        raise HTTPException(400, "所选字段没有可确认的候选值")
    await session.commit()
    await persist_confirmed_memory(
        session,
        key=f"document_candidates:{document.id}",
        value={"accepted": accepted, "filename": document.filename},
        source_type="document_user_confirmed",
        source_id=document.id,
    )
    profile, experiences = await profile_with_experiences(session)
    return profile_response(profile, experiences)


@router.get("/programs", response_model=List[ProgramResponse])
async def list_programs(
    q: str = Query("", max_length=200),
    country: str = Query("", max_length=100),
    field: str = Query("", max_length=160),
    personalized: bool = Query(True),
    session: AsyncSession = Depends(get_session),
) -> List[ProgramResponse]:
    items = await search_programs_for_profile(
        session, q, country, field, use_profile=personalized
    )
    return [await serialize_program(session, item) for item in items]


@router.get("/programs/{program_id}", response_model=ProgramResponse)
async def program_detail(
    program_id: str, session: AsyncSession = Depends(get_session)
) -> ProgramResponse:
    item = await get_program(session, program_id)
    if not item:
        raise HTTPException(404, "项目不存在")
    return await serialize_program(session, item)


@router.post("/programs/{program_id}/verify", response_model=ProgramVerifyResponse)
async def verify_program(
    program_id: str, session: AsyncSession = Depends(get_session)
) -> ProgramVerifyResponse:
    program = await get_program(session, program_id)
    if not program:
        raise HTTPException(404, "项目不存在")
    try:
        source, extracted = await verify_program_official(session, program)
    except (UnsafeUrlError, Exception) as exc:
        raise HTTPException(502, f"官网读取失败：{exc}") from exc
    requirement = await get_requirement(session, program.id)
    return ProgramVerifyResponse(
        program_id=program.id,
        source_id=source.id,
        status="verified" if requirement and requirement.verified else "fetched_needs_review",
        fetched_at=source.fetched_at,
        content_hash=source.content_hash,
        extracted=extracted,
    )


@router.post("/programs/verify-matched", response_model=BatchVerifyResponse)
async def verify_profile_matched_programs(
    limit: int = Query(5, ge=1, le=10),
    session: AsyncSession = Depends(get_session),
) -> BatchVerifyResponse:
    profile, _ = await profile_with_experiences(session)
    if not profile.confirmed or not profile.target_fields or not profile.target_countries:
        raise HTTPException(400, "请先确认画像，并填写目标国家和目标专业方向")
    matched = await search_programs_for_profile(session, use_profile=True)
    results: List[Dict[str, Any]] = []
    for program in matched[:limit]:
        try:
            source, extracted = await verify_program_official(session, program)
            requirement = await get_requirement(session, program.id)
            results.append({
                "program_id": program.id,
                "university": program.university,
                "name": program.name,
                "status": "verified" if requirement and requirement.verified else "fetched_needs_review",
                "source_id": source.id,
                "evidence_count": len(extracted.get("evidence", [])),
                "error": "",
            })
        except Exception as exc:
            results.append({
                "program_id": program.id,
                "university": program.university,
                "name": program.name,
                "status": "failed",
                "source_id": "",
                "evidence_count": 0,
                "error": str(exc)[:300],
            })
    return BatchVerifyResponse(
        matched_count=len(matched),
        attempted_count=len(results),
        verified_count=sum(item["status"] == "verified" for item in results),
        needs_review_count=sum(item["status"] == "fetched_needs_review" for item in results),
        failed_count=sum(item["status"] == "failed" for item in results),
        results=results,
    )


async def serialize_shortlist(session: AsyncSession, item: Shortlist) -> ShortlistResponse:
    rows = list(
        (
            await session.scalars(
                select(ShortlistItem)
                .where(ShortlistItem.shortlist_id == item.id)
                .order_by(ShortlistItem.score.desc())
            )
        ).all()
    )
    output = []
    for row in rows:
        program = await session.get(Program, row.program_id)
        if program:
            output.append(
                ShortlistItemResponse(
                    id=row.id,
                    program=await serialize_program(session, program),
                    tier=row.tier,
                    score=row.score,
                    rationale=row.rationale,
                    risks=row.risks,
                )
            )
    return ShortlistResponse(
        id=item.id,
        name=item.name,
        rationale=item.rationale,
        items=output,
        created_at=item.created_at,
    )


@router.get("/shortlists", response_model=List[ShortlistResponse])
async def list_shortlists(session: AsyncSession = Depends(get_session)) -> List[ShortlistResponse]:
    items = list(
        (
            await session.scalars(
                select(Shortlist)
                .where(Shortlist.owner_id == settings.local_owner_id)
                .order_by(Shortlist.created_at.desc())
            )
        ).all()
    )
    return [await serialize_shortlist(session, item) for item in items]


@router.post("/shortlists", response_model=ShortlistResponse, status_code=201)
async def post_shortlist(
    payload: ShortlistCreate, session: AsyncSession = Depends(get_session)
) -> ShortlistResponse:
    item = await create_shortlist(session, payload.name, payload.program_ids)
    return await serialize_shortlist(session, item)


async def serialize_application_package(
    session: AsyncSession, item: ApplicationPackage
) -> ApplicationPackageResponse:
    program = await get_program(session, item.program_id)
    if not program:
        raise HTTPException(409, "申请包关联的项目不存在")
    return ApplicationPackageResponse(
        id=item.id,
        program=await serialize_program(session, program),
        shortlist_id=item.shortlist_id,
        official_verified=item.official_verified,
        checklist=item.checklist,
        gaps=item.gaps,
        ready=item.ready,
        status=item.status,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("/application-packages", response_model=List[ApplicationPackageResponse])
async def list_application_packages(
    session: AsyncSession = Depends(get_session),
) -> List[ApplicationPackageResponse]:
    items = list((await session.scalars(
        select(ApplicationPackage).where(
            ApplicationPackage.owner_id == settings.local_owner_id
        ).order_by(ApplicationPackage.updated_at.desc())
    )).all())
    output = []
    for item in items:
        item = await get_or_create_application_package(session, item.program_id, item.shortlist_id)
        output.append(await serialize_application_package(session, item))
    await session.commit()
    return output


@router.post(
    "/application-packages/{program_id}/refresh",
    response_model=ApplicationPackageResponse,
)
async def refresh_package(
    program_id: str, session: AsyncSession = Depends(get_session)
) -> ApplicationPackageResponse:
    if not await get_program(session, program_id):
        raise HTTPException(404, "项目不存在")
    item = await get_or_create_application_package(session, program_id)
    await session.commit()
    await session.refresh(item)
    return await serialize_application_package(session, item)


@router.patch(
    "/application-packages/{package_id}/materials",
    response_model=ApplicationPackageResponse,
)
async def update_package_material(
    package_id: str,
    payload: PackageMaterialUpdate,
    session: AsyncSession = Depends(get_session),
) -> ApplicationPackageResponse:
    item = await session.get(ApplicationPackage, package_id)
    if not item or item.owner_id != settings.local_owner_id:
        raise HTTPException(404, "项目申请包不存在")
    allowed = {"ready", "needs_edit", "unverified", "missing", "manual_review"}
    if payload.status not in allowed:
        raise HTTPException(422, "不支持的材料适配状态")
    if payload.status == "ready" and not item.official_verified:
        raise HTTPException(422, "官网材料要求尚未核验，不能标记为符合要求")
    checklist = list(item.checklist or [])
    target = next(
        (row for row in checklist if row.get("material_key") == payload.material_key), None
    )
    if not target:
        raise HTTPException(404, "申请包中没有该材料要求")
    candidates = target.get("candidate_assets", [])
    if payload.status == "ready":
        valid = any(
            row.get("type") == payload.selected_asset_type
            and row.get("id") == payload.selected_asset_id
            for row in candidates
        )
        if not valid:
            raise HTTPException(422, "标记符合要求时必须选择一个实际存在的材料版本")
    target.update({
        "status": payload.status,
        "selected_asset_type": payload.selected_asset_type,
        "selected_asset_id": payload.selected_asset_id,
        "note": payload.note,
    })
    item.checklist = checklist
    item.ready = item.official_verified and all(
        row.get("status") == "ready" and row.get("selected_asset_id")
        for row in checklist
    )
    item.status = "ready" if item.ready else (
        "materials_in_progress" if item.official_verified else "needs_official_verification"
    )
    item.gaps = [
        f"待处理：{row.get('name')}" for row in checklist if row.get("status") != "ready"
    ]
    await session.commit()
    await session.refresh(item)
    return await serialize_application_package(session, item)


@router.get("/material-plans", response_model=List[MaterialPlanResponse])
async def list_material_plans(
    session: AsyncSession = Depends(get_session),
) -> List[MaterialPlanResponse]:
    items = list(
        (
            await session.scalars(
                select(MaterialPlan)
                .where(MaterialPlan.owner_id == settings.local_owner_id)
                .order_by(MaterialPlan.created_at.desc())
            )
        ).all()
    )
    return [MaterialPlanResponse.model_validate(item) for item in items]


@router.post("/material-plans", response_model=MaterialPlanResponse, status_code=201)
async def post_material_plan(
    payload: MaterialPlanCreate, session: AsyncSession = Depends(get_session)
) -> MaterialPlanResponse:
    try:
        item = await create_material_plan(session, payload.program_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return MaterialPlanResponse.model_validate(item)


MATERIAL_KINDS = {"cv", "ps"}
MATERIAL_SCOPES = {"general", "program"}
MATERIAL_STATUSES = {"draft", "ready", "submitted"}


async def serialize_artifact(
    session: AsyncSession, item: MaterialArtifact
) -> MaterialArtifactResponse:
    document = await session.get(Document, item.document_id)
    if not document:
        raise HTTPException(409, "材料版本关联的文件不存在")
    return MaterialArtifactResponse(
        id=item.id,
        document_id=item.document_id,
        program_id=item.program_id,
        kind=item.kind,
        scope=item.scope,
        version_name=item.version_name,
        language=item.language,
        status=item.status,
        notes=item.notes,
        filename=document.filename,
        parse_status=document.parse_status,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def validate_artifact_values(
    kind: str, scope: str, status: str, program_id: Optional[str]
) -> None:
    if kind not in MATERIAL_KINDS:
        raise HTTPException(422, "材料类型只支持 cv 或 ps")
    if scope not in MATERIAL_SCOPES:
        raise HTTPException(422, "版本范围只支持 general 或 program")
    if status not in MATERIAL_STATUSES:
        raise HTTPException(422, "版本状态只支持 draft、ready 或 submitted")
    if scope == "program" and not program_id:
        raise HTTPException(422, "学校定制版本必须关联项目")
    if scope == "general" and program_id:
        raise HTTPException(422, "通用版本不能关联具体项目")


@router.get("/material-artifacts", response_model=List[MaterialArtifactResponse])
async def list_material_artifacts(
    kind: str = Query(""), session: AsyncSession = Depends(get_session)
) -> List[MaterialArtifactResponse]:
    statement = select(MaterialArtifact).where(
        MaterialArtifact.owner_id == settings.local_owner_id
    )
    if kind:
        statement = statement.where(MaterialArtifact.kind == kind)
    items = list((await session.scalars(statement.order_by(MaterialArtifact.updated_at.desc()))).all())
    return [await serialize_artifact(session, item) for item in items]


@router.post("/material-artifacts", response_model=MaterialArtifactResponse, status_code=201)
async def create_material_artifact(
    payload: MaterialArtifactCreate, session: AsyncSession = Depends(get_session)
) -> MaterialArtifactResponse:
    validate_artifact_values(payload.kind, payload.scope, payload.status, payload.program_id)
    document = await session.get(Document, payload.document_id)
    if not document or document.owner_id != settings.local_owner_id:
        raise HTTPException(404, "文件不存在")
    if document.kind != payload.kind:
        raise HTTPException(422, "文件类型与材料版本类型不一致")
    if payload.program_id and not await get_program(session, payload.program_id):
        raise HTTPException(404, "项目不存在")
    item = MaterialArtifact(owner_id=settings.local_owner_id, **payload.model_dump())
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return await serialize_artifact(session, item)


@router.patch("/material-artifacts/{artifact_id}", response_model=MaterialArtifactResponse)
async def update_material_artifact(
    artifact_id: str,
    payload: MaterialArtifactUpdate,
    session: AsyncSession = Depends(get_session),
) -> MaterialArtifactResponse:
    item = await session.get(MaterialArtifact, artifact_id)
    if not item or item.owner_id != settings.local_owner_id:
        raise HTTPException(404, "材料版本不存在")
    values = payload.model_dump(exclude_unset=True)
    kind = item.kind
    scope = str(values.get("scope", item.scope))
    status = str(values.get("status", item.status))
    program_id = values.get("program_id", item.program_id)
    validate_artifact_values(kind, scope, status, program_id)
    if program_id and not await get_program(session, str(program_id)):
        raise HTTPException(404, "项目不存在")
    for key, value in values.items():
        setattr(item, key, value)
    await session.commit()
    await session.refresh(item)
    return await serialize_artifact(session, item)


@router.post("/material-artifacts/preflight", response_model=MaterialPreflightResponse)
async def material_preflight(
    payload: MaterialPreflightRequest, session: AsyncSession = Depends(get_session)
) -> MaterialPreflightResponse:
    item = await session.get(MaterialArtifact, payload.artifact_id)
    if not item or item.owner_id != settings.local_owner_id:
        raise HTTPException(404, "材料版本不存在")
    document = await session.get(Document, item.document_id)
    program = await get_program(session, payload.program_id)
    if not document or not program:
        raise HTTPException(404, "文件或项目不存在")
    checks = [
        {"name": "文件解析成功", "passed": document.parse_status not in {"failed", "pending"}},
        {"name": "材料类型正确", "passed": item.kind in MATERIAL_KINDS},
        {"name": "语言已标注", "passed": bool(item.language.strip())},
        {
            "name": "项目版本匹配",
            "passed": item.scope == "general" or item.program_id == payload.program_id,
        },
        {"name": "版本已确认可提交", "passed": item.status in {"ready", "submitted"}},
    ]
    warnings = []
    if item.scope == "general":
        warnings.append(f"当前是通用 {item.kind.upper()}，提交 {program.name} 前建议确认学校定制内容。")
    if item.status == "submitted":
        warnings.append("该版本已标记为已提交，请确认是否需要重复使用。")
    return MaterialPreflightResponse(
        ready_to_upload=all(bool(check["passed"]) for check in checks),
        artifact_id=item.id,
        program_id=program.id,
        checks=checks,
        warnings=warnings,
    )


@router.get("/material-drafts", response_model=List[MaterialDraftResponse])
async def list_material_drafts(
    kind: str = Query(""), session: AsyncSession = Depends(get_session)
) -> List[MaterialDraft]:
    statement = select(MaterialDraft).where(
        MaterialDraft.owner_id == settings.local_owner_id
    )
    if kind:
        statement = statement.where(MaterialDraft.kind == kind)
    return list(
        (await session.scalars(statement.order_by(MaterialDraft.updated_at.desc()))).all()
    )


@router.get("/material-drafts/{draft_id}/export")
async def export_material_draft(
    draft_id: str,
    format: str = Query("docx", pattern="^(docx|pdf)$"),
    session: AsyncSession = Depends(get_session),
) -> Response:
    item = await session.get(MaterialDraft, draft_id)
    if not item or item.owner_id != settings.local_owner_id:
        raise HTTPException(404, "文稿不存在")
    program = await get_program(session, item.program_id) if item.program_id else None
    filename = export_filename(item, program, format)
    if format == "pdf":
        content = pdf_export(item, program)
        media_type = "application/pdf"
    else:
        content = docx_export(item, program)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": content_disposition(filename)},
    )


@router.post("/material-drafts/generate", response_model=MaterialDraftResponse, status_code=201)
async def generate_material_draft(
    payload: MaterialDraftGenerate, session: AsyncSession = Depends(get_session)
) -> MaterialDraft:
    if payload.kind not in MATERIAL_KINDS:
        raise HTTPException(422, "材料类型只支持 cv 或 ps")
    if payload.language not in {"English", "Chinese"}:
        raise HTTPException(422, "生成语言只支持 English 或 Chinese")
    if check_user_input(payload.prompt):
        raise HTTPException(400, "附加题目包含不安全的指令内容")
    profile, experiences = await profile_with_experiences(session)
    confirmed = [item for item in experiences if item.confirmed]
    if not profile.confirmed:
        raise HTTPException(400, "请先填写并确认申请画像")
    if not confirmed:
        raise HTTPException(400, "请先在画像中添加并确认至少一段真实经历")
    program = None
    if payload.program_id:
        program = await get_program(session, payload.program_id)
        if not program:
            raise HTTPException(404, "项目不存在")
        selected_package = await session.scalar(
            select(ApplicationPackage).where(
                ApplicationPackage.owner_id == settings.local_owner_id,
                ApplicationPackage.program_id == payload.program_id,
            )
        )
        if not selected_package:
            raise HTTPException(400, "该项目尚未加入选校清单，请先选择项目并建立申请包")
    if payload.kind == "ps" and not program:
        raise HTTPException(422, "生成完整 PS 必须选择目标项目")
    generation_input = {
        "kind": payload.kind,
        "language": payload.language,
        "prompt": payload.prompt,
        "profile": {
            "full_name": profile.full_name,
            "current_school": profile.current_school,
            "current_major": profile.current_major,
            "degree": profile.degree,
            "gpa": profile.gpa,
            "gpa_scale": profile.gpa_scale,
            "language_scores": profile.language_scores,
            "target_countries": profile.target_countries,
            "target_fields": profile.target_fields,
            "intake": profile.intake,
        },
        "confirmed_experiences": [
            {
                "id": item.id,
                "kind": item.kind,
                "title": item.title,
                "organization": item.organization,
                "start_date": item.start_date,
                "end_date": item.end_date,
                "description": item.description,
                "tags": item.tags,
            }
            for item in confirmed
        ],
        "program": (
            {
                "id": program.id,
                "university": program.university,
                "name": program.name,
                "field": program.field,
                "official_url": program.official_url,
            }
            if program else None
        ),
    }
    try:
        generated = await provider.generate_material(generation_input)
    except Exception as exc:
        raise HTTPException(502, f"大模型生成失败：{str(exc)[:300]}") from exc
    allowed_ids = {item.id for item in confirmed}
    source_ids = [
        value for value in generated.get("source_experience_ids", []) if value in allowed_ids
    ]
    content = str(generated.get("content", "")).strip()
    findings = verify_output(content)
    if not content or findings:
        raise HTTPException(422, "生成内容未通过完整性或安全检查")
    title = str(generated.get("title") or f"{payload.kind.upper()} draft")[:240]
    version_id = str(uuid4())
    item = MaterialDraft(
        id=version_id,
        owner_id=settings.local_owner_id,
        program_id=program.id if program else None,
        parent_id=None,
        root_id=version_id,
        version_number=1,
        revision_type="generated",
        change_summary="由 AI 根据当前确认画像、经历和目标项目首次生成",
        kind=payload.kind,
        title=title,
        language=payload.language,
        prompt=payload.prompt,
        content=content,
        source_experience_ids=source_ids,
        warnings=list(generated.get("warnings", [])),
        model_info=dict(generated.get("model_info", {})),
        status="draft",
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@router.patch("/material-drafts/{draft_id}", response_model=MaterialDraftResponse, status_code=201)
async def update_material_draft(
    draft_id: str,
    payload: MaterialDraftUpdate,
    session: AsyncSession = Depends(get_session),
) -> MaterialDraft:
    item = await session.get(MaterialDraft, draft_id)
    if not item or item.owner_id != settings.local_owner_id:
        raise HTTPException(404, "文稿不存在")
    values = payload.model_dump(exclude_unset=True)
    if values.get("status") not in {None, "draft", "reviewed"}:
        raise HTTPException(422, "文稿状态只支持 draft 或 reviewed")
    content = values.get("content")
    if content and verify_output(content):
        raise HTTPException(422, "文稿内容未通过安全检查")
    root_id = item.root_id or item.id
    latest_version = await session.scalar(
        select(func.max(MaterialDraft.version_number)).where(
            MaterialDraft.owner_id == settings.local_owner_id,
            MaterialDraft.root_id == root_id,
        )
    )
    changed = []
    if values.get("title") is not None and values["title"] != item.title:
        changed.append("标题")
    if values.get("content") is not None and values["content"] != item.content:
        changed.append("正文")
    if values.get("status") is not None and values["status"] != item.status:
        changed.append("复核状态")
    if not changed:
        raise HTTPException(400, "内容没有变化，无需创建新版本")
    new_item = MaterialDraft(
        owner_id=item.owner_id,
        program_id=item.program_id,
        parent_id=item.id,
        root_id=root_id,
        version_number=int(latest_version or item.version_number) + 1,
        revision_type="manual_edit",
        change_summary=f"人工修改：{'、'.join(changed)}",
        kind=item.kind,
        title=str(values.get("title", item.title)),
        language=item.language,
        prompt=item.prompt,
        content=str(values.get("content", item.content)),
        source_experience_ids=item.source_experience_ids,
        warnings=item.warnings,
        model_info={**item.model_info, "edited_from": item.id},
        status=str(values.get("status", item.status)),
    )
    session.add(new_item)
    await session.commit()
    await session.refresh(new_item)
    return new_item


APPLICATION_STATUSES = {
    "planning",
    "materials",
    "ready",
    "submitted",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
}


def validate_application_status(status: str) -> None:
    if status not in APPLICATION_STATUSES:
        raise HTTPException(422, f"不支持的申请状态：{status}")


@router.get("/applications", response_model=List[ApplicationResponse])
async def list_applications(
    session: AsyncSession = Depends(get_session),
) -> List[ApplicationResponse]:
    items = list(
        (
            await session.scalars(
                select(Application)
                .where(Application.owner_id == settings.local_owner_id)
                .order_by(Application.updated_at.desc())
            )
        ).all()
    )
    return [ApplicationResponse.model_validate(item) for item in items]


@router.post("/applications", response_model=ApplicationResponse, status_code=201)
async def create_application(
    payload: ApplicationCreate, session: AsyncSession = Depends(get_session)
) -> ApplicationResponse:
    validate_application_status(payload.status)
    if not await get_program(session, payload.program_id):
        raise HTTPException(404, "项目不存在")
    package = await session.scalar(select(ApplicationPackage).where(
        ApplicationPackage.owner_id == settings.local_owner_id,
        ApplicationPackage.program_id == payload.program_id,
    ))
    if not package or not package.ready:
        raise HTTPException(400, "该项目申请包尚未就绪，请先核验官网并完成全部必需材料")
    existing = await session.scalar(
        select(Application).where(
            Application.owner_id == settings.local_owner_id,
            Application.program_id == payload.program_id,
        )
    )
    if existing:
        raise HTTPException(409, "该项目已经在申请看板中")
    item = Application(owner_id=settings.local_owner_id, **payload.model_dump())
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return ApplicationResponse.model_validate(item)


@router.patch("/applications/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: str,
    payload: ApplicationUpdate,
    session: AsyncSession = Depends(get_session),
) -> ApplicationResponse:
    item = await session.get(Application, application_id)
    if not item or item.owner_id != settings.local_owner_id:
        raise HTTPException(404, "申请记录不存在")
    values = payload.model_dump(exclude_unset=True)
    if "status" in values and values["status"] is not None:
        validate_application_status(str(values["status"]))
        if values["status"] in {"ready", "submitted", "interview", "offer"}:
            package = await session.scalar(select(ApplicationPackage).where(
                ApplicationPackage.owner_id == settings.local_owner_id,
                ApplicationPackage.program_id == item.program_id,
            ))
            if not package or not package.ready:
                raise HTTPException(400, "项目申请包尚未就绪，不能进入提交阶段")
    for key, value in values.items():
        setattr(item, key, value)
    await session.commit()
    await session.refresh(item)
    return ApplicationResponse.model_validate(item)


@router.get("/tasks", response_model=List[TaskResponse])
async def list_tasks(
    status: str = Query(""), session: AsyncSession = Depends(get_session)
) -> List[TaskResponse]:
    statement = select(Task).where(Task.owner_id == settings.local_owner_id)
    if status:
        statement = statement.where(Task.status == status)
    items = list((await session.scalars(statement.order_by(Task.due_date))).all())
    return [TaskResponse.model_validate(item) for item in items]


@router.post("/tasks", response_model=TaskResponse, status_code=201)
async def post_task(
    payload: TaskCreate, session: AsyncSession = Depends(get_session)
) -> TaskResponse:
    return TaskResponse.model_validate(await create_task(session, payload))


@router.post("/tasks/timeline", response_model=List[TaskResponse], status_code=201)
async def post_timeline(
    payload: TimelineCreate, session: AsyncSession = Depends(get_session)
) -> List[TaskResponse]:
    try:
        items = await create_timeline(session, payload.program_id)
    except ValueError as exc:
        status = 404 if str(exc) == "项目不存在" else 400
        raise HTTPException(status, str(exc)) from exc
    return [TaskResponse.model_validate(item) for item in items]


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def patch_task(
    task_id: str, payload: TaskUpdate, session: AsyncSession = Depends(get_session)
) -> TaskResponse:
    item = await session.get(Task, task_id)
    if not item or item.owner_id != settings.local_owner_id:
        raise HTTPException(404, "任务不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    await session.commit()
    await session.refresh(item)
    return TaskResponse.model_validate(item)


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest, session: AsyncSession = Depends(get_session)
) -> StreamingResponse:
    async def stream():
        queue: asyncio.Queue = asyncio.Queue()

        async def emit(event: str, data: Dict[str, Any]) -> None:
            await queue.put((event, data))

        async def execute() -> None:
            try:
                await harness.run(
                    session=session,
                    message=payload.message,
                    conversation_id=payload.conversation_id,
                    emit=emit,
                    approved_tools=payload.approved_tools,
                )
            except Exception as exc:
                await queue.put(("run.failed", {"error": str(exc)}))
            finally:
                await queue.put(None)

        task = asyncio.create_task(execute())
        while True:
            item = await queue.get()
            if item is None:
                break
            event, data = item
            yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
        await task

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/agent-runs/{run_id}", response_model=AgentRunResponse)
async def get_agent_run(
    run_id: str, session: AsyncSession = Depends(get_session)
) -> AgentRunResponse:
    item = await session.get(AgentRun, run_id)
    if not item or item.owner_id != settings.local_owner_id:
        raise HTTPException(404, "Agent Run 不存在")
    return AgentRunResponse.model_validate(item)


@router.get("/agent-runs/{run_id}/trace", response_model=TraceResponse)
async def get_agent_trace(
    run_id: str, session: AsyncSession = Depends(get_session)
) -> TraceResponse:
    item = await session.get(AgentRun, run_id)
    if not item or item.owner_id != settings.local_owner_id:
        raise HTTPException(404, "Agent Run 不存在")
    steps = list(
        (
            await session.scalars(
                select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.position)
            )
        ).all()
    )
    calls = list(
        (
            await session.scalars(
                select(ToolCall).where(ToolCall.run_id == run_id).order_by(ToolCall.created_at)
            )
        ).all()
    )
    return TraceResponse(
        run=AgentRunResponse.model_validate(item),
        steps=[
            {
                "id": step.id,
                "position": step.position,
                "name": step.name,
                "status": step.status,
                "result": step.result,
            }
            for step in steps
        ],
        tool_calls=[
            {
                "id": call.id,
                "tool_name": call.tool_name,
                "status": call.status,
                "arguments": call.arguments,
                "result": call.result,
                "error": call.error,
                "duration_ms": call.duration_ms,
            }
            for call in calls
        ],
    )


@router.get("/memories", response_model=List[MemoryResponse])
async def list_memories(session: AsyncSession = Depends(get_session)) -> List[MemoryResponse]:
    items = list(
        (
            await session.scalars(
                select(Memory)
                .where(Memory.owner_id == settings.local_owner_id, Memory.active.is_(True))
                .order_by(Memory.updated_at.desc())
            )
        ).all()
    )
    return [MemoryResponse.model_validate(item) for item in items]


@router.delete("/memories/{memory_id}", status_code=204)
async def delete_memory(memory_id: str, session: AsyncSession = Depends(get_session)) -> None:
    item = await session.get(Memory, memory_id)
    if not item or item.owner_id != settings.local_owner_id:
        raise HTTPException(404, "记忆不存在")
    item.active = False
    await session.commit()


@router.get("/skills", response_model=List[SkillResponse])
async def list_skills() -> List[SkillResponse]:
    return [
        SkillResponse(
            name=item.name,
            version=item.version,
            description=item.description,
            tools=item.tools,
            output_schema=item.output_schema,
            enabled=True,
        )
        for item in skill_registry.list()
    ]


@router.get("/mcp/servers", response_model=List[MCPServerResponse])
async def list_mcp_servers(session: AsyncSession = Depends(get_session)) -> List[MCPServerResponse]:
    items = list((await session.scalars(select(MCPConnection))).all())
    return [
        MCPServerResponse(
            name=item.name,
            transport=item.transport,
            endpoint=item.endpoint,
            read_only=item.read_only,
            status=item.status,
            tools=item.tools,
        )
        for item in items
    ]


@router.post("/mcp/demo/call")
async def call_demo_mcp(
    payload: Dict[str, Any], session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    name = str(payload.get("name", ""))
    allowed = {item.name for item in demo_mcp.list_tools()}
    if name not in allowed:
        raise HTTPException(403, "MCP 工具不在只读白名单中")
    registry_name = {
        "catalog.search_programs": "mcp_catalog_search",
    }.get(name)
    if not registry_name:
        raise HTTPException(501, "该 MCP 示例工具尚未映射到统一 Tool Registry")
    run = AgentRun(
        owner_id=settings.local_owner_id,
        skill_name="mcp-demo",
        skill_version="0.1.0",
        goal=f"调用只读 MCP 工具 {name}",
        status="running",
        plan=[
            {
                "id": "step-1",
                "name": "通过统一 Tool Registry 调用 MCP",
                "status": "running",
                "dependencies": [],
                "expected_output": "只读目录结果与 ToolCall Trace",
            }
        ],
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    result = await tool_registry.execute(
        session,
        run.id,
        registry_name,
        payload.get("arguments", {}),
        [registry_name],
    )
    run.status = "completed"
    run.stop_reason = "success"
    run.final_output = "只读 MCP 调用完成"
    run.plan = [{**run.plan[0], "status": "completed"}]
    await session.commit()
    return {
        "server": demo_mcp.name,
        "tool": name,
        "registry_tool": registry_name,
        "run_id": run.id,
        "result": result,
    }
