import feedparser
import httpx
from datetime import datetime
from typing import Optional
from app.core.logging import get_logger

logger = get_logger(__name__)


def _parse_date(entry) -> Optional[datetime]:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6])
        except Exception:
            pass
    return None


def _extract_text(entry) -> str:
    content = ""
    if hasattr(entry, "content") and entry.content:
        content = entry.content[0].get("value", "")
    elif hasattr(entry, "summary"):
        content = entry.summary or ""

    # Strip HTML tags
    from bs4 import BeautifulSoup
    return BeautifulSoup(content, "lxml").get_text(separator="\n", strip=True)


async def scrape_newsletter_source(source: dict) -> list[dict]:
    """Fetch RSS/Atom feed and return article-like dicts."""
    rss_url = source.get("rss_url", "")
    results = []

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(rss_url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            content = resp.text

        feed = feedparser.parse(content)

        for entry in feed.entries[:10]:
            text = _extract_text(entry)
            if len(text) < 100:
                continue

            results.append({
                "url": entry.get("link", ""),
                "title": entry.get("title", ""),
                "raw_text": text[:50000],
                "published_at": _parse_date(entry),
                "source_name": source["name"],
                "metadata": {
                    "scraper": "rss",
                    "feed_url": rss_url,
                },
            })

    except Exception as e:
        logger.warning("newsletter_scrape_failed", source=source.get("name"), error=str(e))

    return results
