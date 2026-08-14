from datetime import date, timedelta
import re
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.entities import (
    ApplicantProfile,
    ApplicationPackage,
    Document,
    Experience,
    MaterialArtifact,
    MaterialDraft,
    MaterialPlan,
    Program,
    ProgramRequirement,
    Shortlist,
    ShortlistItem,
    Task,
)
from app.schemas.api import ProfileUpdate, TaskCreate

DEFAULT_MATERIALS = ["CV", "PS", "成绩单", "推荐信", "语言成绩"]

MATERIAL_ALIASES = {
    "cv": ("CV", "Resume", "Curriculum Vitae", "简历"),
    "ps": ("PS", "Statement of Purpose", "Personal Statement", "Essay", "个人陈述", "文书"),
    "transcript": ("Transcript", "成绩单"),
    "recommendation": ("Recommendation", "Reference", "推荐信"),
    "language": ("TOEFL", "IELTS", "Language", "语言成绩"),
    "writing_sample": ("Writing Sample", "写作样本"),
    "portfolio": ("Portfolio", "作品集"),
    "video_essay": ("Video Essay", "视频文书"),
}


def material_key(name: str) -> str:
    lowered = name.lower()
    for key, aliases in MATERIAL_ALIASES.items():
        if any(alias.lower() in lowered for alias in aliases):
            return key
    return "other_" + "_".join(name.lower().split())[:60]


def material_slots(names: List[str]) -> List[Dict[str, Any]]:
    """Turn official requirements into stable per-program submission slots."""
    prepared_names = [str(value).strip() for value in names if str(value).strip()]
    generic_ps_headings = {
        "ps", "statement of purpose", "personal statement", "essay", "essays",
        "statement of purpose / essays", "personal statement / essays",
        "statement of purpose/essays", "personal statement/essays",
        "个人陈述", "项目文书", "文书",
    }

    def is_generic_ps_heading(value: str) -> bool:
        cleaned = re.sub(r"\s+", " ", value.strip().lower()).strip(" .:：;；-/")
        return cleaned in generic_ps_headings

    specific_ps_requirements = [
        value for value in prepared_names
        if material_key(value) == "ps" and not is_generic_ps_heading(value)
    ]
    if specific_ps_requirements:
        # Official pages often expose a generic “Statement of Purpose / Essays”
        # heading and its full instruction as two list items. The heading is not
        # a second deliverable, so keep only the concrete requirement(s).
        prepared_names = [
            value for value in prepared_names
            if material_key(value) != "ps" or not is_generic_ps_heading(value)
        ]
    ps_total = sum(1 for value in prepared_names if material_key(value) == "ps")
    slots: List[Dict[str, Any]] = []
    counters: Dict[str, int] = {}
    for raw_name in prepared_names:
        name = str(raw_name).strip()
        base_key = material_key(name)
        count = 1
        if base_key == "recommendation":
            number = re.search(r"([1-5])\s*(?:封|份|letters?)?", name, re.IGNORECASE)
            word_number = next((value for word, value in {
                "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
            }.items() if re.search(rf"\b{word}\b", name, re.IGNORECASE) or word in name), None)
            match = int(number.group(1)) if number else word_number
            count = min(5, max(1, match or 1))
        for index in range(count):
            counters[base_key] = counters.get(base_key, 0) + 1
            position = counters[base_key]
            slot_key = base_key if base_key not in {"ps", "recommendation"} and position == 1 else f"{base_key}-{position}"
            label = material_label(base_key, name)
            if base_key == "recommendation":
                label = f"推荐信 {position}"
            elif base_key == "ps":
                label = f"项目文书 {position}" if ps_total > 1 else "项目文书"
            slots.append({
                "material_key": slot_key,
                "slot_key": slot_key,
                "category": base_key,
                "name": label,
                "official_name": name,
                "generatable": base_key in {"cv", "ps", "recommendation"},
            })
    return slots


def material_label(key: str, original: str = "") -> str:
    labels = {
        "cv": "CV / Resume", "ps": "PS / Essays", "transcript": "成绩单",
        "recommendation": "推荐信", "language": "语言成绩",
        "writing_sample": "Writing Sample", "portfolio": "作品集",
        "video_essay": "Video Essay",
    }
    return labels.get(key, original or key)

FIELD_ALIASES = {
    "computer science": {"computer science", "computer engineering", "software engineering", "计算机", "软件工程", "人工智能", "ai"},
    "business": {"business", "management", "商科", "管理"},
    "business analytics": {"business analytics", "商业分析"},
    "finance": {"finance", "financial engineering", "金融", "金融工程"},
    "accounting": {"accounting", "会计"},
    "public policy": {"public policy", "public administration", "公共政策", "公共管理"},
}


def canonical_fields(values: List[str]) -> List[str]:
    matches = []
    for value in values:
        lowered = value.strip().lower()
        for canonical, aliases in FIELD_ALIASES.items():
            if any(alias in lowered or lowered in alias for alias in aliases):
                matches.append(canonical)
    matches = list(dict.fromkeys(matches))
    # “Business Analytics”等具体方向也包含 business 字样；具体方向存在时不能再扩展为
    # 整个商科目录，否则精确搜索会混入金融、会计项目。
    if "business" in matches and any(
        item in matches for item in ("business analytics", "finance", "accounting")
    ):
        matches.remove("business")
    return matches


def program_matches_fields(program: Program, values: List[str]) -> bool:
    requested = canonical_fields(values)
    if not requested:
        return True
    if "business" in requested and program.field in {"Business Analytics", "Finance", "Accounting"}:
        return True
    program_fields = set(canonical_fields([program.field]))
    return bool(set(requested) & program_fields)


async def get_or_create_profile(session: AsyncSession) -> ApplicantProfile:
    profile = await session.scalar(
        select(ApplicantProfile).where(ApplicantProfile.owner_id == settings.local_owner_id)
    )
    if profile is None:
        profile = ApplicantProfile(owner_id=settings.local_owner_id)
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
    return profile


async def profile_with_experiences(session: AsyncSession) -> tuple:
    profile = await get_or_create_profile(session)
    experiences = list(
        (
            await session.scalars(
                select(Experience)
                .where(Experience.profile_id == profile.id)
                .order_by(Experience.start_date.desc())
            )
        ).all()
    )
    return profile, experiences


async def update_profile(session: AsyncSession, payload: ProfileUpdate) -> tuple:
    profile = await get_or_create_profile(session)
    fields = payload.model_dump(exclude={"experiences"})
    for key, value in fields.items():
        setattr(profile, key, value)
    await session.execute(delete(Experience).where(Experience.profile_id == profile.id))
    for item in payload.experiences:
        values = item.model_dump(exclude={"id"})
        session.add(
            Experience(
                profile_id=profile.id,
                owner_id=settings.local_owner_id,
                **values,
            )
        )
    await session.commit()
    return await profile_with_experiences(session)


async def search_programs(
    session: AsyncSession,
    query: str = "",
    country: str = "",
    field: str = "",
) -> List[Program]:
    statement = select(Program).where(Program.active.is_(True))
    if query:
        pattern = f"%{query}%"
        statement = statement.where(
            or_(
                Program.name.ilike(pattern),
                Program.university.ilike(pattern),
                Program.field.ilike(pattern),
            )
        )
    if country:
        statement = statement.where(Program.country == country)
    if field:
        statement = statement.where(Program.field.ilike(f"%{field}%"))
    return list((await session.scalars(statement.order_by(Program.university))).all())


async def search_programs_for_profile(
    session: AsyncSession,
    query: str = "",
    country: str = "",
    field: str = "",
    use_profile: bool = True,
) -> List[Program]:
    profile = await get_or_create_profile(session)
    if (
        use_profile
        and not query
        and not field
        and not country
        and (
            not profile.confirmed
            or not profile.target_fields
            or not profile.target_countries
        )
    ):
        return []
    query_fields = canonical_fields([query]) if query else []
    requested_fields = [field] if field else (query_fields or (
        (profile.target_fields or ([profile.current_major] if profile.current_major else []))
        if use_profile and not query else []
    ))
    requested_countries = [country] if country else (profile.target_countries if use_profile and not query else [])
    # “master computer science” 这类自然语言不是项目名，先识别专业语义再筛选；
    # 没识别出专业时才按学校、项目名和字段做普通关键词搜索。
    items = await search_programs(
        session, query="" if query_fields else query, country="", field=""
    )
    if requested_countries:
        items = [item for item in items if item.country in requested_countries]
    if requested_fields:
        items = [item for item in items if program_matches_fields(item, requested_fields)]
    return items


async def get_program(session: AsyncSession, program_id: str) -> Optional[Program]:
    return await session.get(Program, program_id)


async def get_requirement(session: AsyncSession, program_id: str) -> Optional[ProgramRequirement]:
    return await session.scalar(
        select(ProgramRequirement).where(ProgramRequirement.program_id == program_id)
    )


async def score_program(
    profile: ApplicantProfile, program: Program, requirement: Optional[ProgramRequirement]
) -> tuple:
    score = 68.0
    reasons = []
    risks = []
    if profile.target_countries and program.country in profile.target_countries:
        score += 8
        reasons.append("符合目标国家")
    if profile.target_fields and any(
        target.lower() in program.field.lower() or program.field.lower() in target.lower()
        for target in profile.target_fields
    ):
        score += 10
        reasons.append("专业方向匹配")
    if profile.budget and program.tuition:
        if program.tuition <= profile.budget:
            score += 5
            reasons.append("学费在预算范围内")
        else:
            score -= 8
            risks.append("学费可能超过当前预算")
    if requirement and requirement.min_gpa is not None:
        if profile.gpa is None:
            risks.append("尚未填写 GPA，无法判断硬性门槛")
        elif profile.gpa >= requirement.min_gpa:
            score += 5
            reasons.append("达到公开 GPA 门槛")
        else:
            score -= 30
            risks.append(f"当前 GPA 低于公开门槛 {requirement.min_gpa}")
    if requirement and not requirement.verified:
        risks.append("项目要求尚未完成官网重新核验")
    score = max(0, min(100, score))
    tier = "reach" if score < 70 else "target" if score < 85 else "safer"
    return score, tier, reasons or ["与当前申请方向存在基础匹配"], risks


async def score_recommendation(
    profile: ApplicantProfile,
    experiences: List[Experience],
    program: Program,
    requirement: Optional[ProgramRequirement],
) -> tuple[float, List[str]]:
    """Rank candidates using every confirmed profile signal that the catalog can compare."""
    score = 45.0
    reasons: List[str] = []

    if profile.target_countries and program.country in profile.target_countries:
        score += 12
        reasons.append("符合目标国家")
    if profile.target_fields and any(
        target.lower() in program.field.lower() or program.field.lower() in target.lower()
        for target in profile.target_fields
    ):
        score += 18
        reasons.append("专业方向匹配")

    if profile.budget and program.tuition:
        if program.tuition <= profile.budget:
            score += 6
            reasons.append("学费在预算范围内")
        else:
            score -= min(15, 5 + (program.tuition - profile.budget) / profile.budget * 10)

    if requirement and requirement.min_gpa is not None and profile.gpa is not None:
        if profile.gpa >= requirement.min_gpa:
            score += 6
            reasons.append("GPA 达到官网要求")
        else:
            score -= 20

    if profile.current_major and program_matches_fields(program, [profile.current_major]):
        score += 5
        reasons.append("与当前专业背景衔接")

    confirmed = [item for item in experiences if item.confirmed]
    if confirmed:
        score += min(6, len(confirmed) * 1.5)
        kinds = {item.kind for item in confirmed}
        labels = []
        for key, label in (
            ("research", "科研"),
            ("internship", "实习"),
            ("project", "项目"),
            ("award", "奖项"),
            ("course", "课程"),
        ):
            if key in kinds:
                labels.append(label)
        reasons.append(f"结合已确认的{'、'.join(labels[:3]) or '经历'}素材")

    language = requirement.language if requirement else {}
    met_languages = []
    for test_name in ("TOEFL", "IELTS", "GRE", "GMAT"):
        applicant_score = profile.language_scores.get(test_name)
        required_score = language.get(test_name)
        if applicant_score is not None and required_score is not None:
            if float(applicant_score) >= float(required_score):
                score += 4
                met_languages.append(test_name)
            else:
                score -= 10
    if met_languages:
        reasons.append(f"当前{'/'.join(met_languages)}成绩达到官网要求")

    preference_text = " ".join(str(value) for value in profile.preferences.values()).lower()
    if program.city and program.city.lower() in preference_text:
        score += 3
        reasons.append("城市偏好匹配")

    if profile.intake:
        reasons.append(f"面向 {profile.intake} 申请规划")

    return max(0, min(100, score)), list(dict.fromkeys(reasons))


async def recommendation_candidates(
    session: AsyncSession,
    query: str = "",
    limit: int = 5,
    excluded_program_ids: Optional[Set[str]] = None,
) -> List[tuple[Program, float, List[str]]]:
    profile, experiences = await profile_with_experiences(session)
    programs = await search_programs_for_profile(session, query=query, use_profile=not bool(query))
    excluded_program_ids = excluded_program_ids or set()
    programs = [
        program for program in programs if program.id not in excluded_program_ids
    ]
    ranked = []
    for program in programs:
        requirement = await get_requirement(session, program.id)
        score, reasons = await score_recommendation(
            profile, experiences, program, requirement
        )
        ranked.append((program, score, reasons))
    ranked.sort(key=lambda item: (-item[1], item[0].university, item[0].name))
    return ranked[:limit]


async def create_shortlist(session: AsyncSession, name: str, program_ids: List[str]) -> Shortlist:
    profile = await get_or_create_profile(session)
    shortlist = Shortlist(name=name, owner_id=settings.local_owner_id)
    session.add(shortlist)
    await session.flush()
    rationales = []
    for program_id in dict.fromkeys(program_ids):
        program = await get_program(session, program_id)
        if not program:
            continue
        requirement = await get_requirement(session, program_id)
        score, tier, reasons, risks = await score_program(profile, program, requirement)
        rationale = "；".join(reasons)
        rationales.append(f"{program.university}：{rationale}")
        session.add(
            ShortlistItem(
                shortlist_id=shortlist.id,
                program_id=program.id,
                tier=tier,
                score=score,
                rationale=rationale,
                risks=risks,
                owner_id=settings.local_owner_id,
            )
        )
        await get_or_create_application_package(session, program.id, shortlist.id)
    shortlist.rationale = "基于目标国家、专业、预算和已核验硬性条件生成。"
    await session.commit()
    await session.refresh(shortlist)
    return shortlist


async def add_shortlist_programs(
    session: AsyncSession, program_ids: List[str], name: str = "我的选校与申请包"
) -> Shortlist:
    shortlist = await consolidate_shortlists(session)
    if shortlist is None:
        shortlist = Shortlist(name=name, owner_id=settings.local_owner_id)
        session.add(shortlist)
        await session.flush()

    existing_ids = set(
        (
            await session.scalars(
                select(ShortlistItem.program_id).where(
                    ShortlistItem.shortlist_id == shortlist.id
                )
            )
        ).all()
    )
    profile, experiences = await profile_with_experiences(session)
    for program_id in dict.fromkeys(program_ids):
        if program_id in existing_ids:
            continue
        program = await get_program(session, program_id)
        if not program:
            continue
        requirement = await get_requirement(session, program_id)
        score, reasons = await score_recommendation(
            profile, experiences, program, requirement
        )
        _, tier, _, risks = await score_program(profile, program, requirement)
        session.add(
            ShortlistItem(
                shortlist_id=shortlist.id,
                program_id=program.id,
                tier=tier,
                score=score,
                rationale="；".join(reasons),
                risks=risks,
                owner_id=settings.local_owner_id,
            )
        )
        await get_or_create_application_package(session, program.id, shortlist.id)
    shortlist.rationale = "基于完整画像、已确认经历和官网原文证据生成。"
    await session.commit()
    await session.refresh(shortlist)
    return shortlist


async def consolidate_shortlists(session: AsyncSession) -> Optional[Shortlist]:
    """Collapse legacy one-shot shortlists into the current persistent collection."""
    shortlists = list(
        (
            await session.scalars(
                select(Shortlist)
                .where(Shortlist.owner_id == settings.local_owner_id)
                .order_by(Shortlist.created_at.desc())
            )
        ).all()
    )
    if not shortlists:
        return None
    primary = shortlists[0]
    primary.name = "我的选校与申请包"
    all_ids = [item.id for item in shortlists]
    rows = list(
        (
            await session.scalars(
                select(ShortlistItem)
                .where(ShortlistItem.shortlist_id.in_(all_ids))
                .order_by(ShortlistItem.created_at.desc())
            )
        ).all()
    )
    seen: set[str] = set()
    for row in rows:
        if row.program_id in seen:
            await session.delete(row)
            continue
        seen.add(row.program_id)
        row.shortlist_id = primary.id
    packages = list(
        (
            await session.scalars(
                select(ApplicationPackage).where(
                    ApplicationPackage.owner_id == settings.local_owner_id,
                    ApplicationPackage.shortlist_id.in_(all_ids),
                )
            )
        ).all()
    )
    for package in packages:
        package.shortlist_id = primary.id
    for legacy in shortlists[1:]:
        await session.delete(legacy)
    primary.rationale = "基于完整画像、已确认经历和官网原文证据生成。"
    await session.commit()
    await session.refresh(primary)
    return primary


async def remove_shortlist_program(
    session: AsyncSession, shortlist_id: str, program_id: str
) -> bool:
    item = await session.scalar(
        select(ShortlistItem).where(
            ShortlistItem.shortlist_id == shortlist_id,
            ShortlistItem.program_id == program_id,
            ShortlistItem.owner_id == settings.local_owner_id,
        )
    )
    if item is None:
        return False
    await session.delete(item)
    package = await session.scalar(
        select(ApplicationPackage).where(
            ApplicationPackage.owner_id == settings.local_owner_id,
            ApplicationPackage.program_id == program_id,
            ApplicationPackage.shortlist_id == shortlist_id,
        )
    )
    if package is not None:
        await session.delete(package)
    await session.commit()
    return True


async def _initial_assets(session: AsyncSession, program_id: str) -> dict:
    documents = list(
        (await session.scalars(select(Document).where(
            Document.owner_id == settings.local_owner_id,
            Document.parse_status.notin_(["failed", "pending"]),
        ).order_by(Document.created_at.desc()))).all()
    )
    artifacts = list(
        (await session.scalars(select(MaterialArtifact).where(
            MaterialArtifact.owner_id == settings.local_owner_id,
        ))).all()
    )
    drafts = list(
        (await session.scalars(select(MaterialDraft).where(
            MaterialDraft.owner_id == settings.local_owner_id,
        ).order_by(MaterialDraft.updated_at.desc()))).all()
    )
    draft_program_ids = {draft.program_id for draft in drafts if draft.program_id}
    draft_programs = list((await session.scalars(
        select(Program).where(Program.id.in_(draft_program_ids))
    )).all()) if draft_program_ids else []
    program_labels = {
        program.id: f"{program.university} · {program.name}"
        for program in draft_programs
    }
    by_key = {key: [] for key in MATERIAL_ALIASES}
    by_key.setdefault("recommendation", [])
    for document in documents:
        key = material_key(document.kind)
        if key in by_key:
            by_key[key].append({"type": "document", "id": document.id, "label": document.filename})
    for artifact in artifacts:
        if artifact.kind in by_key and (
            artifact.scope == "general" or artifact.program_id == program_id
        ):
            by_key[artifact.kind].append({"type": "artifact", "id": artifact.id, "label": artifact.version_name})
    for draft in drafts:
        if draft.kind in by_key:
            scope = "general" if draft.program_id is None else (
                "current_program" if draft.program_id == program_id else "other_program"
            )
            source_program = program_labels.get(draft.program_id or "", "")
            source_suffix = f" · 来源：{source_program}" if source_program else ""
            status_suffix = " · 草稿" if draft.status != "reviewed" else ""
            by_key[draft.kind].append({
                "type": "draft",
                "id": draft.id,
                "label": f"{draft.title} v{draft.version_number}{source_suffix}{status_suffix}",
                "program_id": draft.program_id,
                "scope": scope,
                "status": draft.status,
            })
    return by_key


async def refresh_application_package(
    session: AsyncSession, package: ApplicationPackage
) -> ApplicationPackage:
    requirement = await get_requirement(session, package.program_id)
    official_verified = bool(requirement and requirement.verified)
    names = list(requirement.materials) if requirement and requirement.materials else DEFAULT_MATERIALS
    unique = material_slots([str(name) for name in names])
    assets = await _initial_assets(session, package.program_id)
    previous = {item.get("material_key"): item for item in (package.checklist or [])}
    checklist = []
    used_recommendation_assets: Set[str] = set()
    selection_changed = False
    for base in unique:
        key = base["material_key"]
        category = base.get("category", key)
        old = previous.get(key, {})
        candidates = assets.get(category, [])
        status = old.get("status")
        selected_type = old.get("selected_asset_type", "")
        selected_id = old.get("selected_asset_id", "")
        selected_exists = any(
            candidate.get("type") == selected_type and candidate.get("id") == selected_id
            for candidate in candidates
        )
        if selected_id and not selected_exists:
            selected_type = ""
            selected_id = ""
            status = "unverified" if candidates else "missing"
        elif status == "missing" and candidates:
            status = "unverified"
        if not selected_id and candidates:
            available = [
                candidate for candidate in candidates
                if candidate.get("type") != "draft" or candidate.get("status") == "reviewed"
            ]
            if category == "recommendation":
                available = [candidate for candidate in candidates if candidate.get("id") not in used_recommendation_assets]
            elif category == "ps":
                # A generic uploaded PS is useful as reference, but must not be silently
                # treated as a project-ready submission. Only project-scoped artifacts or
                # reviewed generated drafts can become the automatic default.
                available = [
                    candidate for candidate in available
                    if candidate.get("type") == "artifact" or (
                        candidate.get("type") == "draft"
                        and candidate.get("scope") in {"general", "current_program"}
                    )
                ]
            recommended = available[0] if available else None
            if recommended:
                selected_type = str(recommended.get("type", ""))
                selected_id = str(recommended.get("id", ""))
                status = "ready"
                selection_changed = True
        if category == "recommendation" and selected_id:
            used_recommendation_assets.add(selected_id)
        if status not in {"ready", "needs_edit", "unverified", "missing", "manual_review"}:
            status = "unverified" if candidates else "missing"
        checklist.append({
            **base,
            "required": True,
            "status": status,
            "source_verified": official_verified,
            "candidate_assets": candidates,
            "selected_asset_type": selected_type,
            "selected_asset_id": selected_id,
            "note": old.get("note", ""),
        })
    gaps = []
    for item in checklist:
        if item["status"] == "missing":
            gaps.append(f"缺少：{item['name']}")
        elif item["status"] in {"needs_edit", "unverified", "manual_review"}:
            gaps.append(f"待处理：{item['name']}")
    package.official_verified = official_verified
    package.checklist = checklist
    package.gaps = gaps
    if selection_changed:
        package.plan_confirmed = False
    selections_complete = bool(checklist) and all(
        item["status"] == "ready" and item.get("selected_asset_id") for item in checklist
    )
    package.ready = package.plan_confirmed and selections_complete
    package.status = "ready" if package.ready else "materials_in_progress"
    await session.flush()
    return package


async def get_or_create_application_package(
    session: AsyncSession, program_id: str, shortlist_id: Optional[str] = None
) -> ApplicationPackage:
    package = await session.scalar(select(ApplicationPackage).where(
        ApplicationPackage.owner_id == settings.local_owner_id,
        ApplicationPackage.program_id == program_id,
    ))
    if package is None:
        package = ApplicationPackage(
            owner_id=settings.local_owner_id, program_id=program_id,
            shortlist_id=shortlist_id, checklist=[], gaps=[],
        )
        session.add(package)
        await session.flush()
    elif shortlist_id and not package.shortlist_id:
        package.shortlist_id = shortlist_id
    return await refresh_application_package(session, package)


async def create_material_plan(session: AsyncSession, program_id: str) -> MaterialPlan:
    program = await get_program(session, program_id)
    if not program:
        raise ValueError("项目不存在")
    requirement = await get_requirement(session, program_id)
    _, experiences = await profile_with_experiences(session)
    materials = (
        requirement.materials if requirement and requirement.materials else DEFAULT_MATERIALS
    )
    checklist = [
        {
            "name": item,
            "required": True,
            "status": "todo",
            "source_verified": bool(requirement and requirement.verified),
        }
        for item in materials
    ]
    confirmed = [item for item in experiences if item.confirmed]
    selected = [
        {
            "experience_id": item.id,
            "title": item.title,
            "kind": item.kind,
            "reason": f"可支持 {program.field} 方向的能力证明",
        }
        for item in confirmed[:5]
    ]
    gaps = []
    if not confirmed:
        gaps.append("经历库中没有已确认经历，请先补充科研、实习或项目经历")
    if not requirement or not requirement.verified:
        gaps.append("材料要求尚未完成官网核验")
    plan = MaterialPlan(
        owner_id=settings.local_owner_id,
        program_id=program_id,
        checklist=checklist,
        cv_plan={
            "selected_experiences": selected,
            "recommended_order": [item["title"] for item in selected],
            "focus": f"突出与 {program.field} 相关的技术深度、成果和量化影响",
            "grounded": True,
        },
        ps_plan={
            "prompt": "请以学校官网实际 PS 题目为准；当前为通用规划。",
            "selected_experiences": selected[:3],
            "outline": ["申请动机", "能力证据", "项目匹配", "学习与职业目标"],
            "customization": f"具体说明 {program.name} 的课程或研究资源如何支持目标",
            "grounded": True,
        },
        gaps=gaps,
    )
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    return plan


def parse_deadline(value: Optional[str]) -> date:
    if not value:
        raise ValueError("项目截止日期尚未通过官网证据核验，不能生成带日期的申请时间线")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("项目截止日期格式无效，请重新核验官网") from exc


async def create_timeline(session: AsyncSession, program_id: str) -> List[Task]:
    program = await get_program(session, program_id)
    if not program:
        raise ValueError("项目不存在")
    package = await session.scalar(select(ApplicationPackage).where(
        ApplicationPackage.owner_id == settings.local_owner_id,
        ApplicationPackage.program_id == program_id,
    ))
    if not package or not package.ready:
        raise ValueError("项目申请包材料尚未就绪，不能进入申请执行")
    requirement = await get_requirement(session, program_id)
    if not requirement or not requirement.verified:
        raise ValueError("项目截止日期和材料要求尚未完成官网核验，不能生成正式时间线")
    deadline = parse_deadline(requirement.deadline)
    milestones = [
        ("核验项目要求", "research", 100, "high"),
        ("确认 CV 经历与结构", "cv", 75, "high"),
        ("完成 PS 提纲与初稿", "ps", 60, "high"),
        ("确认推荐人并跟进推荐信", "recommendation", 50, "medium"),
        ("整理成绩单与语言成绩", "document", 35, "medium"),
        ("完成网申提交前检查", "application", 7, "high"),
    ]
    tasks = []
    for title, category, days_before, priority in milestones:
        item = Task(
            owner_id=settings.local_owner_id,
            program_id=program_id,
            title=f"{program.university}｜{title}",
            category=category,
            status="todo",
            due_date=(deadline - timedelta(days=days_before)).isoformat(),
            priority=priority,
            details=f"根据项目截止日期 {deadline.isoformat()} 自动生成。",
        )
        session.add(item)
        tasks.append(item)
    await session.commit()
    for item in tasks:
        await session.refresh(item)
    return tasks


async def create_task(session: AsyncSession, payload: TaskCreate) -> Task:
    item = Task(owner_id=settings.local_owner_id, **payload.model_dump())
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item
