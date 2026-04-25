import re
import hashlib
from typing import Optional
from app.core.logging import get_logger

logger = get_logger(__name__)

_seen_hashes: set[str] = set()  # in-memory dedup within a run


def _content_hash(text: str) -> str:
    return hashlib.md5(text[:500].encode()).hexdigest()


def clean_text(text: str) -> str:
    """Normalize whitespace, strip URLs, remove boilerplate."""
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    # Remove cookie/privacy banners (common patterns)
    text = re.sub(r"(accept cookies|privacy policy|terms of service|subscribe to our newsletter).*", "", text, flags=re.IGNORECASE)
    # Remove excessive punctuation runs
    text = re.sub(r"[.]{3,}", "...", text)
    return text.strip()


def is_duplicate(text: str) -> bool:
    h = _content_hash(text)
    if h in _seen_hashes:
        return True
    _seen_hashes.add(h)
    return False


def is_low_quality(text: str, min_words: int = 50) -> bool:
    return len(text.split()) < min_words


def clean_raw_content(raw: dict) -> Optional[dict]:
    """Clean a raw content dict. Returns None if content should be discarded."""
    text = raw.get("raw_text", "")
    if not text:
        return None

    text = clean_text(text)

    if is_low_quality(text):
        logger.debug("discarded_low_quality", url=raw.get("url"))
        return None

    if is_duplicate(text):
        logger.debug("discarded_duplicate", url=raw.get("url"))
        return None

    raw["raw_text"] = text
    return raw


def reset_dedup_cache() -> None:
    """Reset the dedup cache between pipeline runs."""
    _seen_hashes.clear()
