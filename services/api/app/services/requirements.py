import asyncio
import re
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import EvidenceChunk, Program, ProgramRequirement, ProgramSource
from app.services.web import fetch_page

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
MATERIAL_KEYWORDS = {
    "CV / Resume": ["resume", "curriculum vitae", "cv"],
    "Statement of Purpose / Essays": ["statement of purpose", "personal statement", "essay"],
    "Transcripts": ["transcript"],
    "Recommendations": ["recommendation", "reference letter"],
    "English proficiency": ["toefl", "ielts", "english proficiency"],
    "GRE / GMAT": ["gre", "gmat"],
    "Portfolio": ["portfolio"],
}


def _admission_evidence_valid(field: str, quote: str) -> bool:
    """Reject numbers/material mentions that describe graduation or page navigation."""
    lowered = quote.lower()
    if field == "deadline":
        return any(word in lowered for word in ("application", "admission", "apply", "round"))
    if field == "min_gpa":
        if any(word in lowered for word in ("maintain", "qpa", "good standing", "graduate", "degree requirement")):
            return False
        return any(word in lowered for word in ("admission", "applicant", "application", "undergraduate", "minimum", "required"))
    if field in {"TOEFL", "IELTS"}:
        return not any(word in lowered for word in ("graduate from", "degree requirement"))
    if field == "materials":
        return any(word in lowered for word in ("submit", "upload", "application", "required", "provide", "must include"))
    if field == "prerequisites":
        return any(word in lowered for word in ("prerequisite", "preparation", "background", "applicant", "admission", "expected"))
    return True


def _lines(text: str) -> List[str]:
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def _first_line(lines: List[str], patterns: List[str]) -> Optional[str]:
    for line in lines:
        lowered = line.lower()
        if any(re.search(pattern, lowered, re.I) for pattern in patterns):
            return line[:1000]
    return None


def _deadline(line: Optional[str]) -> Optional[str]:
    if not line:
        return None
    match = re.search(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,\s*|\s+)(20\d{2})",
        line,
        re.I,
    )
    if match:
        return f"{int(match.group(3)):04d}-{MONTHS[match.group(1).lower()]:02d}-{int(match.group(2)):02d}"
    match = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", line)
    if match:
        return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    return None


def _deadline_candidates(lines: List[str]) -> List[Dict[str, str]]:
    """Extract dates from deadline sections, including table rows where the label is separate."""
    candidates: List[Dict[str, str]] = []
    context_remaining = 0
    for line in lines:
        lowered = line.lower()
        has_deadline_label = bool(
            lowered.strip() == "deadline"
            or re.search(r"application deadline|deadline[:\s]|round \d", lowered)
        )
        if has_deadline_label:
            # 正文清洗后，表头和日期之间可能夹着较长的说明段落。
            context_remaining = 40
        normalized = _deadline(line)
        if normalized and (has_deadline_label or context_remaining > 0):
            round_match = re.search(r"(?:round|priority)\s*([\w-]+)", line, re.I)
            candidates.append({
                "date": normalized, "raw": line,
                "round": round_match.group(0) if round_match else "",
            })
        if context_remaining > 0:
            context_remaining -= 1
    return list({(item["date"], item["raw"]): item for item in candidates}.values())[:20]


def extract_requirement_candidates(text: str) -> Dict[str, Any]:
    lines = _lines(text)
    deadlines = _deadline_candidates(lines)
    deadline_line = deadlines[0]["raw"] if deadlines else None
    tuition_line = _first_line(lines, [r"tuition.{0,80}\$", r"\$.{0,30}tuition", r"tuition and fees"])
    fee_line = _first_line(lines, [r"application fee.{0,50}\$", r"\$.{0,20}application fee"])
    gpa_line = _first_line(lines, [r"(?:minimum|required|admission|applicant|undergraduate).{0,50}gpa", r"gpa.{0,30}\d\.\d"])
    if gpa_line and not _admission_evidence_valid("min_gpa", gpa_line):
        gpa_line = None
    toefl_line = _first_line(lines, [r"toefl.{0,50}\d{2,3}"])
    ielts_line = _first_line(lines, [r"ielts.{0,50}\d(?:\.\d)?"])

    def money(line: Optional[str]) -> Optional[float]:
        if not line:
            return None
        match = re.search(r"\$\s*([\d,]{3,})", line)
        return float(match.group(1).replace(",", "")) if match else None

    def score(line: Optional[str], label: str, pattern: str) -> Optional[float]:
        if not line:
            return None
        match = re.search(pattern, line, re.I)
        return float(match.group(1)) if match else None

    materials, material_quotes = [], []
    for label, keywords in MATERIAL_KEYWORDS.items():
        quote = _first_line(
            lines,
            [rf"(?:submit|upload|application|required|provide|must include).{{0,160}}\b{re.escape(keyword)}\b|\b{re.escape(keyword)}\b.{{0,160}}(?:submit|upload|required|provide)" for keyword in keywords],
        )
        if quote:
            materials.append(label)
            material_quotes.append(quote)

    prerequisite_quotes = [
        line for line in lines
        if re.search(r"prerequisite|required preparation|quantitative preparation", line, re.I)
    ][:8]
    evidence = []
    values = {
        "deadline": (deadline_line, _deadline(deadline_line)),
        "tuition": (tuition_line, money(tuition_line)),
        "application_fee": (fee_line, money(fee_line)),
        "min_gpa": (gpa_line, score(gpa_line, "GPA", r"(?:GPA[^\d]{0,20})(\d\.\d{1,2})")),
        "TOEFL": (toefl_line, score(toefl_line, "TOEFL", r"TOEFL[^\d]{0,30}(\d{2,3})")),
        "IELTS": (ielts_line, score(ielts_line, "IELTS", r"IELTS[^\d]{0,30}(\d(?:\.\d)?)")),
    }
    for field, (quote, value) in values.items():
        if quote and value is not None:
            item = {"field": field, "quote": quote, "value": value, "confidence": 0.75}
            if field == "deadline":
                item["admission_context"] = True
            evidence.append(item)
    for quote in dict.fromkeys(material_quotes):
        evidence.append({"field": "materials", "quote": quote, "value": "官网材料要求", "confidence": 0.7})
    for quote in prerequisite_quotes:
        evidence.append({"field": "prerequisites", "quote": quote, "value": "先修要求", "confidence": 0.65})
    for deadline_item in deadlines:
        line, normalized = deadline_item["raw"], deadline_item["date"]
        if not any(item["field"] == "deadline" and item["quote"] == line for item in evidence):
            evidence.append({
                "field": "deadline", "quote": line, "value": normalized,
                "confidence": 0.75, "admission_context": True,
            })
    return {
        "deadline_raw": deadline_line or "",
        "deadline": values["deadline"][1],
        "deadlines": deadlines,
        "tuition": values["tuition"][1],
        "currency": "USD" if values["tuition"][1] is not None else "",
        "min_gpa": values["min_gpa"][1],
        "language": {
            key: values[key][1] for key in ("TOEFL", "IELTS") if values[key][1] is not None
        },
        "materials": materials,
        "prerequisites": prerequisite_quotes,
        "fees": {
            "application_fee": values["application_fee"][1], "currency": "USD"
        } if values["application_fee"][1] is not None else {},
        "evidence": evidence,
    }


def merge_ai_extraction(rule_data: Dict[str, Any], ai_data: Dict[str, Any], text: str) -> Dict[str, Any]:
    valid_evidence = []
    for item in ai_data.get("evidence", []):
        quote = str(item.get("quote", "")).strip()
        if quote and quote in text and _admission_evidence_valid(str(item.get("field", "")), quote):
            valid_evidence.append(item)
    evidenced = {item.get("field") for item in valid_evidence}
    merged = dict(rule_data)
    for field in ["deadline_raw", "deadline", "tuition", "currency", "min_gpa", "language", "materials", "prerequisites", "fees"]:
        value = ai_data.get(field)
        field_evidenced = field in evidenced or (field == "language" and evidenced & {"TOEFL", "IELTS"})
        if value not in (None, "", [], {}) and field_evidenced:
            merged[field] = value
    accepted = {
        "deadline", "tuition", "application_fee", "min_gpa", "TOEFL", "IELTS",
        "materials", "prerequisites",
    }
    merged["evidence"] = list({
        item["quote"]: item
        for item in [*rule_data.get("evidence", []), *valid_evidence]
        if item.get("field") in accepted
    }.values())
    return merged


def sanitize_extraction_by_evidence(data: Dict[str, Any], text: str) -> Dict[str, Any]:
    """Make every persisted requirement field depend on exact, admission-scoped evidence."""
    cleaned = dict(data)
    evidence = [
        item for item in data.get("evidence", [])
        if str(item.get("quote", "")).strip() in text
        and (
            bool(item.get("admission_context"))
            or _admission_evidence_valid(
                str(item.get("field", "")), str(item.get("quote", ""))
            )
        )
    ]
    fields = {str(item.get("field")) for item in evidence}
    if "deadline" not in fields:
        cleaned["deadline_raw"], cleaned["deadline"], cleaned["deadlines"] = "", None, []
    else:
        cleaned["deadlines"] = [
            item for item in (cleaned.get("deadlines") or [])
            if item.get("raw") in text and _deadline(item.get("raw")) == item.get("date")
        ]
        if not cleaned["deadlines"] and cleaned.get("deadline"):
            cleaned["deadlines"] = [{
                "date": cleaned["deadline"], "raw": cleaned.get("deadline_raw", ""), "round": ""
            }]
    if "tuition" not in fields:
        cleaned["tuition"], cleaned["currency"] = None, ""
    if "min_gpa" not in fields:
        cleaned["min_gpa"] = None
    cleaned["language"] = {
        key: value for key, value in (cleaned.get("language") or {}).items() if key in fields
    }
    if "materials" not in fields:
        cleaned["materials"] = []
    if "prerequisites" not in fields:
        cleaned["prerequisites"] = []
    if "application_fee" not in fields:
        cleaned["fees"] = {}
    cleaned["evidence"] = evidence
    return cleaned


async def fetch_official_source(session: AsyncSession, program: Program) -> ProgramSource:
    page = await fetch_page(program.official_url)
    source = ProgramSource(
        program_id=program.id, url=page.url, title=page.title,
        content_hash=page.content_hash, content=page.text, status="fetched",
    )
    session.add(source)
    await session.flush()
    return source


async def fetch_official_sources(
    session: AsyncSession, program: Program, limit: int = 4
) -> List[ProgramSource]:
    """Fetch the exact program page plus the most relevant official requirement pages."""
    primary_page = await fetch_page(program.official_url)
    pages = [primary_page]
    ranked = sorted(
        primary_page.related_links,
        key=lambda item: (
            0 if any(key in f"{item['label']} {item['url']}".lower()
                     for key in ("admission", "application", "requirement", "deadline")) else 1,
            0 if any(key in f"{item['label']} {item['url']}".lower()
                     for key in ("tuition", "fee", "cost")) else 1,
        ),
    )
    results = await asyncio.gather(
        *(fetch_page(item["url"]) for item in ranked[: max(0, limit - 1)]),
        return_exceptions=True,
    )
    pages.extend(page for page in results if not isinstance(page, Exception))
    sources = []
    for page in pages:
        source = ProgramSource(
            program_id=program.id, url=page.url, title=page.title,
            content_hash=page.content_hash, content=page.text, status="fetched",
        )
        session.add(source)
        await session.flush()
        sources.append(source)
    return sources


async def extract_source_requirements(program: Program, source: ProgramSource) -> Dict[str, Any]:
    extracted = extract_requirement_candidates(source.content)
    try:
        from app.agent.provider import provider
        if provider.available:
            ai_data = await provider.extract_program_requirements(program, source.content)
            extracted = merge_ai_extraction(extracted, ai_data, source.content)
    except Exception as exc:
        extracted["ai_extraction_error"] = str(exc)[:300]
    return sanitize_extraction_by_evidence(extracted, source.content)


def merge_source_extractions(items: List[tuple]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {
        "deadline_raw": "", "deadline": None, "tuition": None, "currency": "",
        "min_gpa": None, "language": {}, "materials": [], "prerequisites": [],
        "fees": {}, "evidence": [], "deadlines": [], "source_results": [],
    }
    for source, data in items:
        merged["source_results"].append({
            "source_id": source.id, "url": source.url,
            "fields": sorted({item["field"] for item in data.get("evidence", [])}),
        })
        for field in ("deadline_raw", "deadline", "tuition", "currency", "min_gpa"):
            if merged[field] in (None, "") and data.get(field) not in (None, ""):
                merged[field] = data[field]
        for deadline in data.get("deadlines") or []:
            merged["deadlines"].append({
                **deadline, "source_id": source.id, "url": source.url,
            })
        merged["language"].update(data.get("language") or {})
        merged["fees"].update(data.get("fees") or {})
        for field in ("materials", "prerequisites"):
            merged[field] = list(dict.fromkeys([*merged[field], *(data.get(field) or [])]))
        for evidence in data.get("evidence", []):
            merged["evidence"].append({**evidence, "source_id": source.id, "url": source.url})
    merged["deadlines"] = list({
        (item["date"], item["source_id"]): item for item in merged["deadlines"]
        if item.get("date") and item["date"] >= date.today().isoformat()
    }.values())
    merged["deadlines"].sort(key=lambda item: item["date"])
    if merged["deadlines"]:
        merged["deadline"] = merged["deadlines"][0]["date"]
        merged["deadline_raw"] = merged["deadlines"][0].get("raw", "")
    elif merged.get("deadline") and merged["deadline"] < date.today().isoformat():
        # Keep the verbatim evidence quote, but never promote an inferred or
        # historical year into the structured current-cycle deadline field.
        merged["deadline"] = None
        merged["deadline_raw"] = ""
    return merged


async def extract_and_save_requirements(
    session: AsyncSession, program: Program, source: ProgramSource
) -> Dict[str, Any]:
    extracted = await extract_source_requirements(program, source)

    requirement = await session.scalar(
        select(ProgramRequirement).where(ProgramRequirement.program_id == program.id)
    )
    if requirement is None:
        requirement = ProgramRequirement(program_id=program.id)
        session.add(requirement)
    # 每次核验都以本次官网证据为准。抽取不到即为未知，不能保留旧演示值或猜测值。
    requirement.deadline = extracted.get("deadline")
    requirement.deadline_raw = extracted.get("deadline_raw", "")
    requirement.deadlines = extracted.get("deadlines") or []
    requirement.min_gpa = extracted.get("min_gpa")
    for field in ("language", "materials", "prerequisites", "fees"):
        setattr(requirement, field, extracted.get(field) or ([] if field in {"materials", "prerequisites"} else {}))
    program.tuition = extracted.get("tuition")
    if program.tuition is not None:
        program.currency = extracted.get("currency") or program.currency
    requirement.source_ids = list(dict.fromkeys([*(requirement.source_ids or []), source.id]))
    await session.execute(delete(EvidenceChunk).where(EvidenceChunk.source_id == source.id))
    for item in extracted.get("evidence", []):
        session.add(EvidenceChunk(
            program_id=program.id, source_id=source.id, field=item["field"],
            quote=item["quote"][:5000], locator=source.url,
            confidence=float(item.get("confidence", 0.7)),
        ))
    core = {item["field"] for item in extracted.get("evidence", [])}
    requirement.verified = "deadline" in core and "materials" in core
    source.status = "verified" if requirement.verified else "fetched_needs_review"
    await session.commit()
    return extracted


async def verify_program_official(session: AsyncSession, program: Program) -> tuple:
    sources = await fetch_official_sources(session, program)
    extracted_values = await asyncio.gather(
        *(extract_source_requirements(program, source) for source in sources)
    )
    extracted_items = list(zip(sources, extracted_values))
    extracted = merge_source_extractions(extracted_items)
    requirement = await session.scalar(
        select(ProgramRequirement).where(ProgramRequirement.program_id == program.id)
    )
    if requirement is None:
        requirement = ProgramRequirement(program_id=program.id)
        session.add(requirement)
    requirement.deadline = extracted.get("deadline")
    requirement.deadline_raw = extracted.get("deadline_raw", "")
    requirement.deadlines = extracted.get("deadlines") or []
    requirement.min_gpa = extracted.get("min_gpa")
    for field in ("language", "materials", "prerequisites", "fees"):
        setattr(requirement, field, extracted.get(field) or ([] if field in {"materials", "prerequisites"} else {}))
    program.tuition = extracted.get("tuition")
    if program.tuition is not None:
        program.currency = extracted.get("currency") or program.currency
    requirement.source_ids = [source.id for source in sources]
    # 综合核验是一个新快照：删除该项目上一次的字段证据，避免旧页面或旧申请周期
    # 的 quote 与当前结果同时显示。来源页历史仍保留，便于审计抓取记录。
    await session.execute(
        delete(EvidenceChunk).where(EvidenceChunk.program_id == program.id)
    )
    for item in extracted.get("evidence", []):
        session.add(EvidenceChunk(
            program_id=program.id, source_id=item["source_id"], field=item["field"],
            quote=item["quote"][:5000], locator=item["url"],
            confidence=float(item.get("confidence", 0.7)),
        ))
    core = {item["field"] for item in extracted.get("evidence", [])}
    requirement.verified = "deadline" in core and "materials" in core
    for source in sources:
        source.status = "verified" if requirement.verified else "fetched_needs_review"
    await session.commit()
    await session.refresh(sources[0])
    return sources[0], extracted
