from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional
import httpx
from app.core.logging import get_logger

logger = get_logger(__name__)


async def scrape_url(url: str, timeout: int = 30000) -> Optional[dict]:
    """Scrape a URL and return cleaned text content."""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (compatible; GenAIBot/1.0)"})
            await page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)
            html = await page.content()
            await browser.close()

        soup = BeautifulSoup(html, "lxml")

        # Remove noise elements
        for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()

        title = ""
        if soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)
        elif soup.find("title"):
            title = soup.find("title").get_text(strip=True)

        # Try to extract main content
        main = (
            soup.find("main") or
            soup.find("article") or
            soup.find(class_=["post-content", "article-content", "entry-content", "content"]) or
            soup.find("body")
        )
        text = main.get_text(separator="\n", strip=True) if main else ""

        # Basic published date extraction
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
            "raw_text": text[:50000],  # cap at 50k chars
            "published_at": published_at,
            "metadata": {"scraper": "playwright"},
        }

    except Exception as e:
        logger.warning("scrape_failed", url=url, error=str(e))
        return None


async def scrape_website_source(source: dict) -> list[dict]:
    """Scrape a website source config and return list of article dicts."""
    results = []
    base_url = source["url"]

    # First scrape the index page to find article links
    index_data = await scrape_url(base_url)
    if not index_data:
        return []

    # Re-parse to extract links
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(base_url, timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)
            html = await page.content()
            await browser.close()

        soup = BeautifulSoup(html, "lxml")
        links = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/"):
                from urllib.parse import urljoin
                href = urljoin(base_url, href)
            if base_url.split("/")[2] in href and href != base_url:
                links.add(href)

        # Scrape up to 3 article links
        for link in list(links)[:3]:
            data = await scrape_url(link)
            if data and len(data.get("raw_text", "")) > 200:
                data["source_name"] = source["name"]
                results.append(data)

    except Exception as e:
        logger.warning("website_scrape_failed", source=source["name"], error=str(e))

    return results
