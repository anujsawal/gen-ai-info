from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
from datetime import datetime
from typing import Optional
import httpx
import re
from app.core.logging import get_logger

logger = get_logger(__name__)


def _extract_video_id(url: str) -> Optional[str]:
    patterns = [
        r"(?:v=|youtu\.be/|embed/)([a-zA-Z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


async def get_channel_videos(channel_id: str, max_videos: int = 5) -> list[dict]:
    """Fetch recent video metadata from a YouTube channel using RSS feed."""
    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(rss_url)
            resp.raise_for_status()

        import feedparser
        feed = feedparser.parse(resp.text)
        videos = []
        for entry in feed.entries[:max_videos]:
            video_id = entry.get("yt_videoid", "")
            videos.append({
                "video_id": video_id,
                "title": entry.get("title", ""),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "published_at": datetime(*entry.published_parsed[:6]) if hasattr(entry, "published_parsed") else None,
                "channel": feed.feed.get("title", ""),
            })
        return videos
    except Exception as e:
        logger.warning("channel_rss_failed", channel_id=channel_id, error=str(e))
        return []


async def get_transcript(video_id: str) -> Optional[str]:
    """Get English transcript for a YouTube video."""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US"])
        return " ".join(entry["text"] for entry in transcript)
    except (NoTranscriptFound, TranscriptsDisabled):
        return None
    except Exception as e:
        logger.warning("transcript_failed", video_id=video_id, error=str(e))
        return None


async def scrape_youtube_source(source: dict) -> list[dict]:
    """Scrape a YouTube channel source config and return article-like dicts."""
    channel_id = source.get("channel_id", "")
    max_videos = source.get("max_videos_per_run", 3)

    videos = await get_channel_videos(channel_id, max_videos)
    results = []

    for video in videos:
        transcript = await get_transcript(video["video_id"])
        if not transcript:
            continue

        results.append({
            "url": video["url"],
            "title": video["title"],
            "raw_text": transcript[:50000],
            "published_at": video.get("published_at"),
            "source_name": source["name"],
            "metadata": {
                "scraper": "youtube",
                "video_id": video["video_id"],
                "channel": video.get("channel", ""),
            },
        })

    return results
