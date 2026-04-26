import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse
import re
from app.core.logging import get_logger

logger = get_logger(__name__)

# Only follow links that look like article/post pages, not nav/utility pages
ARTICLE_PATH_RE = re.compile(
    r'/(?:blog|news|post|posts|article|articles|research|paper|papers|\d{4})/|/\d{4}[-/]\d{2}',
    re.IGNORECASE,
)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; GenAIBot/1.0)"}


async def scrape_url(url: str, timeout: int = 15) -> Optional[dict]:
    """Fetch a URL with httpx and return cleaned text content."""
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            r = await client.get(url, headers=_HEADERS)
            r.raise_for_status()
            html = r.text

        soup = BeautifulSoup(html, "lxml")

        for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()

        title = ""
        if soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)
        elif soup.find("title"):
            title = soup.find("title").get_text(strip=True)

        main = (
            soup.find("main") or
            soup.find("article") or
            soup.find(class_=["post-content", "article-content", "entry-content", "content"]) or
            soup.find("body")
        )
        text = main.get_text(separator="\n", strip=True) if main else ""

        published_at = None
        for meta in soup.find_all("meta"):
            if meta.get("property") in ["article:published_time", "og:published_time"]:
                try:
                    published_at = datetime.fromisoformat(meta["content"].replace("Z", "+00:00"))
                except Exception:
                    pass

        return {
            "url": url,
            "title": title,
            "raw_text": text[:50000],
            "published_at": published_at,
            "metadata": {"scraper": "playwright"},  # keep value — ingestion_graph uses it for source type
        }

    except Exception as e:
        logger.warning("scrape_failed", url=url, error=str(e))
        return None


def _is_article_link(href: str, base_domain: str) -> bool:
    """Return True only for links that look like article pages on the same domain."""
    try:
        parsed = urlparse(href)
        if parsed.netloc and parsed.netloc != base_domain:
            return False
        path = parsed.path
        # Must match an article-like path pattern
        return bool(ARTICLE_PATH_RE.search(path))
    except Exception:
        return False


async def scrape_website_source(source: dict) -> list[dict]:
    """Scrape a website source config and return list of article dicts."""
    results = []
    base_url = source["url"]
    base_domain = urlparse(base_url).netloc

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(base_url, headers=_HEADERS)
            r.raise_for_status()
            html = r.text

        soup = BeautifulSoup(html, "lxml")
        links: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/"):
                href = urljoin(base_url, href)
            if _is_article_link(href, base_domain):
                links.add(href)

        scrape_depth = source.get("scrape_depth", 1)
        limit = min(scrape_depth * 3, 5)  # max 5 articles per source per run

        for link in list(links)[:limit]:
            data = await scrape_url(link)
            if data and len(data.get("raw_text", "").split()) > 100:
                data["source_name"] = source["name"]
                results.append(data)

    except Exception as e:
        logger.warning("website_scrape_failed", source=source.get("name"), error=str(e))

    logger.info("website_scrape_done", source=source.get("name"), articles=len(results))
    return results
