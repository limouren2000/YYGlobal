from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.entities import Memory


async def persist_confirmed_memory(
    session: AsyncSession,
    key: str,
    value: Dict[str, Any],
    source_type: str,
    source_id: str,
    memory_type: str = "semantic",
) -> Memory:
    existing_items = list((await session.scalars(
        select(Memory).where(
            Memory.owner_id == settings.local_owner_id,
            Memory.memory_type == memory_type,
            Memory.key == key,
            Memory.active.is_(True),
        ).order_by(Memory.updated_at.desc())
    )).all())
    matching = next((item for item in existing_items if item.value == value), None)
    if matching:
        for item in existing_items:
            if item.id != matching.id:
                item.active = False
        await session.commit()
        await session.refresh(matching)
        return matching
    for item in existing_items:
        item.active = False
    item = Memory(
        owner_id=settings.local_owner_id,
        memory_type=memory_type,
        key=key,
        value=value,
        source_type=source_type,
        source_id=source_id,
        confidence=1.0,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item
