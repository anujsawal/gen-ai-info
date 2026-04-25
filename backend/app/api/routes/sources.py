from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from app.db.session import get_db
from app.db.models import Source, SourceType
import uuid

router = APIRouter(prefix="/sources", tags=["sources"])


class SourceCreate(BaseModel):
    name: str
    url: Optional[str] = None
    type: SourceType
    active: bool = True
    fetch_config: dict = {}


@router.get("")
async def list_sources(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Source).order_by(Source.created_at))
    sources = result.scalars().all()
    return [
        {
            "id": s.id, "name": s.name, "url": s.url, "type": s.type.value,
            "active": s.active, "last_fetched_at": s.last_fetched_at.isoformat() if s.last_fetched_at else None,
        }
        for s in sources
    ]


@router.post("")
async def create_source(data: SourceCreate, db: AsyncSession = Depends(get_db)):
    source = Source(id=str(uuid.uuid4()), **data.model_dump())
    db.add(source)
    await db.commit()
    return {"id": source.id, "name": source.name}


@router.patch("/{source_id}/toggle")
async def toggle_source(source_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(404, "Source not found")
    source.active = not source.active
    await db.commit()
    return {"id": source_id, "active": source.active}


@router.delete("/{source_id}")
async def delete_source(source_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(404, "Source not found")
    await db.delete(source)
    await db.commit()
    return {"deleted": source_id}
