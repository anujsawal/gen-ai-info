from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, Any
from app.db.session import get_db
from app.db.models import Source, SourceType
import uuid
import re
import httpx

router = APIRouter(prefix="/sources", tags=["sources"])


class SourceCreate(BaseModel):
    name: str
    url: Optional[str] = None
    type: SourceType
    active: bool = True
    fetch_config: dict = {}


class DetectRequest(BaseModel):
    url: str


async def _probe_rss(url: str) -> Optional[str]:
    """Return RSS feed URL if one is discoverable from the given page."""
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            html = r.text
        match = re.search(
            r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]+href=["\']([^"\']+)["\']',
            html, re.IGNORECASE
        ) or re.search(
            r'<link[^>]+href=["\']([^"\']+)["\'][^>]+type=["\']application/(?:rss|atom)\+xml["\']',
            html, re.IGNORECASE
        )
        if match:
            href = match.group(1)
            if href.startswith("http"):
                return href
            base = "/".join(url.split("/")[:3])
            return base + href if href.startswith("/") else base + "/" + href
    except Exception:
        pass
    return None


def _extract_youtube_channel_id(url: str) -> Optional[str]:
    m = re.search(r"youtube\.com/channel/(UC[\w-]+)", url)
    return m.group(1) if m else None


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


@router.post("/detect")
async def detect_source(payload: DetectRequest) -> dict[str, Any]:
    """Detect source type and config from a URL."""
    url = payload.url.strip()

    # YouTube
    if "youtube.com" in url or "youtu.be" in url:
        channel_id = _extract_youtube_channel_id(url)
        result: dict[str, Any] = {
            "type": "youtube",
            "url": url,
            "fetch_config": {"max_videos_per_run": 2},
        }
        if channel_id:
            result["fetch_config"]["channel_id"] = channel_id
        else:
            # Try to extract channel_id from page HTML
            try:
                async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
                    r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                m = re.search(r'"channelId"\s*:\s*"(UC[\w-]+)"', r.text)
                if m:
                    result["fetch_config"]["channel_id"] = m.group(1)
            except Exception:
                pass
        return result

    # ArXiv
    if "arxiv.org" in url:
        return {
            "type": "arxiv",
            "url": url,
            "fetch_config": {"categories": ["cs.AI"], "max_papers_per_run": 3},
        }

    # Try RSS probe
    rss_url = await _probe_rss(url)
    if rss_url:
        return {"type": "newsletter", "url": rss_url, "fetch_config": {}}

    # Fallback: website
    return {"type": "website", "url": url, "fetch_config": {"scrape_depth": 1}}
