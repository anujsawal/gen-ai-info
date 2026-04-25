"""
Responsible AI checks: content moderation, source bias detection, PII screening.
"""
import re
from collections import Counter
from app.core.logging import get_logger

logger = get_logger(__name__)

HARMFUL_PATTERNS = [
    r"\b(hate speech|incite|violence against|kill all)\b",
]

BIAS_THRESHOLD = 0.60  # flag if one source accounts for >60% of content


def check_content_moderation(text: str) -> dict:
    """Basic keyword-based content moderation."""
    flags = []
    for pattern in HARMFUL_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            flags.append(f"Matched pattern: {pattern}")

    return {"safe": len(flags) == 0, "flags": flags}


def check_source_bias(articles: list[dict]) -> dict:
    """Check if content is over-concentrated from one source."""
    if not articles:
        return {"biased": False, "source_distribution": {}}

    sources = [a.get("source_name", "unknown") for a in articles]
    counts = Counter(sources)
    total = len(sources)
    distribution = {src: round(count / total, 2) for src, count in counts.items()}

    biased_sources = [src for src, share in distribution.items() if share > BIAS_THRESHOLD]

    return {
        "biased": len(biased_sources) > 0,
        "biased_sources": biased_sources,
        "source_distribution": distribution,
        "recommendation": f"Consider adding more diverse sources to balance {biased_sources}" if biased_sources else None,
    }


def screen_for_pii(text: str) -> dict:
    """Simple regex-based PII detection (email, phone numbers)."""
    patterns = {
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
    }
    detected = {}
    for pii_type, pattern in patterns.items():
        matches = re.findall(pattern, text)
        if matches:
            detected[pii_type] = len(matches)

    return {"pii_detected": len(detected) > 0, "types_found": detected}


def run_responsible_ai_checks(articles: list[dict]) -> dict:
    """Run all responsible AI checks on a batch of articles."""
    all_text = " ".join(a.get("raw_text", "") for a in articles)

    moderation = check_content_moderation(all_text)
    bias = check_source_bias(articles)
    pii = screen_for_pii(all_text)

    passed = moderation["safe"] and not pii["pii_detected"]
    report = {
        "passed": passed,
        "content_moderation": moderation,
        "source_bias": bias,
        "pii_screening": pii,
    }

    if not passed:
        logger.warning("responsible_ai_check_failed", report=report)

    return report
