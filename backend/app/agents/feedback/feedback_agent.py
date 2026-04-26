"""
Feedback Curator Agent — routes user newsletter feedback to the right pipeline agent.

Deduplicates via embedding cosine similarity (>0.85 = skip).
Marks feedback as "applied" after it is injected into a newsletter generation run.
"""
import uuid
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.db.models import NewsletterFeedback
from app.agents.processing.embedder import embed_query
from app.core.logging import get_logger

logger = get_logger(__name__)

_DEDUP_THRESHOLD = 0.85

# Keywords that determine which agent should receive the feedback.
# A comment can match multiple agents.
_PM_KEYWORDS = {
    "story", "topic", "coverage", "vendor", "diverse", "diversity",
    "always about", "too much", "include", "exclude", "variety",
    "openai", "anthropic", "google", "meta", "boring topics",
    "biased", "bias", "missing",
}
_DEVELOPER_KEYWORDS = {
    "writing", "sentence", "headline", "tone", "verbose", "unclear",
    "wording", "format", "style", "hard to read", "badly written",
    "too long", "too short", "boring writing", "jargon",
}
_QA_KEYWORDS = {
    "wrong", "incorrect", "hallucination", "fact", "claim",
    "misleading", "false", "made up", "inaccurate", "error",
    "not true", "outdated",
}


def _route_comment(comment: str) -> dict[str, list[str]]:
    lower = comment.lower()
    routed: dict[str, list[str]] = {}
    if any(kw in lower for kw in _PM_KEYWORDS):
        routed["pm"] = [comment]
    if any(kw in lower for kw in _DEVELOPER_KEYWORDS):
        routed["developer"] = [comment]
    if any(kw in lower for kw in _QA_KEYWORDS):
        routed["qa"] = [comment]
    # Default: send to PM if no keyword matched (most editorial complaints end up there)
    if not routed:
        routed["pm"] = [comment]
    return routed


def _cosine(a: list[float], b) -> float:
    a_arr = np.array(a, dtype=np.float32)
    b_arr = np.array(b, dtype=np.float32)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))


class FeedbackCuratorAgent:
    async def process_feedback(
        self,
        db: AsyncSession,
        newsletter_id: str,
        rating: int,
        comment: str | None,
    ) -> dict:
        """
        Store and route user feedback. Returns routing outcome.
        """
        entry_id = str(uuid.uuid4())

        # Positive signal with no comment — nothing actionable
        if rating >= 4 and not comment:
            fb = NewsletterFeedback(
                id=entry_id,
                newsletter_id=newsletter_id,
                rating=rating,
                comment=None,
                embedding=None,
                status="applied",
                routed_to=None,
            )
            db.add(fb)
            await db.commit()
            logger.info("feedback_positive_no_comment", newsletter_id=newsletter_id, rating=rating)
            return {"status": "applied", "message": "Positive signal recorded"}

        # Low rating with no comment — generic PM signal
        if not comment:
            routed_to = {"pm": [f"User gave low rating ({rating}/5) — no specific comment"]}
            fb = NewsletterFeedback(
                id=entry_id,
                newsletter_id=newsletter_id,
                rating=rating,
                comment=None,
                embedding=None,
                status="routed",
                routed_to=routed_to,
            )
            db.add(fb)
            await db.commit()
            logger.info("feedback_low_rating_no_comment", newsletter_id=newsletter_id, rating=rating)
            return {"status": "routed", "routed_to": routed_to}

        # Embed the comment
        embedding = embed_query(comment)

        # Deduplication: check cosine similarity against existing embeddings
        rows = await db.execute(
            select(NewsletterFeedback.embedding)
            .where(
                NewsletterFeedback.embedding.is_not(None),
                NewsletterFeedback.status.in_(["routed", "applied"]),
            )
        )
        existing_embeddings = [r[0] for r in rows.fetchall()]

        for existing_emb in existing_embeddings:
            sim = _cosine(embedding, existing_emb)
            if sim > _DEDUP_THRESHOLD:
                fb = NewsletterFeedback(
                    id=entry_id,
                    newsletter_id=newsletter_id,
                    rating=rating,
                    comment=comment,
                    embedding=embedding,
                    status="duplicate",
                    routed_to=None,
                )
                db.add(fb)
                await db.commit()
                logger.info("feedback_duplicate", newsletter_id=newsletter_id, similarity=round(sim, 3))
                return {"status": "duplicate", "message": "Similar feedback already recorded"}

        # Route to the appropriate agent(s)
        routed_to = _route_comment(comment)
        # Prefix low-rating comments for emphasis
        if rating <= 2:
            routed_to = {
                agent: [f"(Rating {rating}/5) {c}" for c in comments]
                for agent, comments in routed_to.items()
            }

        fb = NewsletterFeedback(
            id=entry_id,
            newsletter_id=newsletter_id,
            rating=rating,
            comment=comment,
            embedding=embedding,
            status="routed",
            routed_to=routed_to,
        )
        db.add(fb)
        await db.commit()
        logger.info("feedback_routed", newsletter_id=newsletter_id, rating=rating, agents=list(routed_to.keys()))
        return {"status": "routed", "routed_to": routed_to}

    async def get_curated_context(self, db: AsyncSession) -> dict:
        """
        Returns all pending routed feedback grouped by target agent.
        Called at the start of each newsletter generation run.
        """
        rows = await db.execute(
            select(NewsletterFeedback)
            .where(NewsletterFeedback.status == "routed")
            .order_by(NewsletterFeedback.created_at.desc())
            .limit(20)
        )
        entries = rows.scalars().all()

        curated: dict[str, list[str]] = {"pm": [], "qa": [], "developer": []}
        for entry in entries:
            if not entry.routed_to:
                continue
            for agent, comments in entry.routed_to.items():
                if agent in curated:
                    curated[agent].extend(comments)

        # Remove empty lists so callers can use truthiness checks
        return {k: v for k, v in curated.items() if v}
