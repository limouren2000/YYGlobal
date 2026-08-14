from pathlib import Path
from typing import Any, Dict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.agent.provider import provider
from app.models.entities import Conversation, Document, MaterialDraft, Memory, Message, Program, Task
from app.services.business import profile_with_experiences


async def build_context(
    session: AsyncSession,
    skill_name: str,
    goal: str,
    conversation: Conversation | None = None,
) -> Dict[str, Any]:
    profile, experiences = await profile_with_experiences(session)
    memories = list(
        (
            await session.scalars(
                select(Memory)
                .where(Memory.owner_id == settings.local_owner_id, Memory.active.is_(True))
                .order_by(Memory.updated_at.desc())
                .limit(20)
            )
        ).all()
    )
    unique_memories: Dict[str, Memory] = {}
    for item in memories:
        unique_memories.setdefault(f"{item.memory_type}:{item.key}", item)
    program_count = await session.scalar(select(func.count()).select_from(Program))
    open_tasks = await session.scalar(
        select(func.count())
        .select_from(Task)
        .where(Task.owner_id == settings.local_owner_id, Task.status != "done")
    )
    resource_ids = set(conversation.resource_ids or []) if conversation else set()
    conversation_history = list((await session.scalars(select(Message).where(
        Message.owner_id == settings.local_owner_id,
        Message.conversation_id == conversation.id,
    ).order_by(Message.created_at))).all()) if conversation else []
    for message in conversation_history:
        if message.role != "user":
            continue
        for source in message.sources or []:
            if source.get("type") == "document" and source.get("id"):
                resource_ids.add(f"document:{source['id']}")
            elif source.get("type") in {"draft", "reference_draft"} and source.get("id"):
                resource_ids.add(f"draft:{source['id']}")
    document_ids = {
        value.removeprefix("document:") for value in resource_ids
        if value.startswith("document:")
    }
    draft_ids = {
        value.removeprefix("draft:") for value in resource_ids
        if value.startswith("draft:")
    }
    documents = list((await session.scalars(select(Document).where(
        Document.owner_id == settings.local_owner_id,
        Document.id.in_(document_ids),
    ))).all()) if document_ids else []
    for item in documents:
        if not item.extracted_text.strip() and provider.available and Path(item.path).is_file():
            try:
                extracted = await provider.extract_document(Path(item.path), item.mime_type, item.kind, "")
                summary = str(extracted.get("summary") or "").strip()
                if summary:
                    item.extracted_data = extracted
                    item.extracted_text = summary[:200_000]
                    item.parse_status = "parsed_multimodal"
            except Exception:
                pass
    drafts = list((await session.scalars(select(MaterialDraft).where(
        MaterialDraft.owner_id == settings.local_owner_id,
        MaterialDraft.id.in_(draft_ids),
    ))).all()) if draft_ids else []
    return {
        "goal": goal,
        "skill": skill_name,
        "profile": {
            "full_name": profile.full_name,
            "school": profile.current_school,
            "major": profile.current_major,
            "degree": profile.degree,
            "gpa": profile.gpa,
            "gpa_scale": profile.gpa_scale,
            "language_scores": profile.language_scores,
            "target_countries": profile.target_countries,
            "target_fields": profile.target_fields,
            "intake": profile.intake,
            "budget": profile.budget,
            "preferences": profile.preferences,
            "confirmed": profile.confirmed,
        },
        "experiences": [
            {
                "id": item.id,
                "kind": item.kind,
                "title": item.title,
                "organization": item.organization,
                "description": item.description,
                "confirmed": item.confirmed,
            }
            for item in experiences[:20]
        ],
        "memories": [
            {
                "type": item.memory_type,
                "key": item.key,
                "value": item.value,
                "source": item.source_type,
            }
            for item in unique_memories.values()
        ],
        "conversation_history": [
            {"role": item.role, "content": item.content}
            for item in conversation_history
        ],
        "resource_ids": list(resource_ids),
        "reference_documents": [{
            "id": item.id,
            "filename": item.filename,
            "kind": item.kind,
            "content": (item.extracted_text or str((item.extracted_data or {}).get("summary") or ""))[:20_000],
        } for item in documents],
        "reference_drafts": [{
            "id": item.id,
            "title": item.title,
            "kind": item.kind,
            "program_id": item.program_id,
            "content": item.content[:20_000],
        } for item in drafts],
        "catalog": {"program_count": program_count or 0},
        "tasks": {"open_count": open_tasks or 0},
        "context_policy": {
            "facts_only": True,
            "unconfirmed_values_are_not_facts": True,
            "token_budget": settings.agent_context_token_budget,
        },
    }
