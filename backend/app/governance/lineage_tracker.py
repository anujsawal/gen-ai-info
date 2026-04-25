"""
Data lineage tracking: source_url → raw_content → article → chunk → newsletter
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.db.models import RawContent, Article, Chunk, Newsletter, AuditLog
from app.core.logging import get_logger

logger = get_logger(__name__)


async def get_article_lineage(article_id: str, db: AsyncSession) -> dict:
    """Full lineage for one article: raw → article → chunks → newsletters."""
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        return {"error": "Article not found"}

    raw_result = await db.execute(select(RawContent).where(RawContent.id == article.raw_content_id))
    raw = raw_result.scalar_one_or_none()

    chunk_result = await db.execute(select(Chunk).where(Chunk.article_id == article_id))
    chunks = chunk_result.scalars().all()

    audit_result = await db.execute(
        select(AuditLog).where(AuditLog.entity_id == article_id).order_by(AuditLog.created_at)
    )
    audits = audit_result.scalars().all()

    return {
        "article_id": article_id,
        "lineage": {
            "source": {
                "url": raw.url if raw else None,
                "scraped_at": raw.scraped_at.isoformat() if raw else None,
            },
            "processing": {
                "raw_content_id": article.raw_content_id,
                "cluster_id": article.cluster_id,
                "embedding_model": "nomic-embed-text-v1",
            },
            "article": {
                "title": article.title,
                "category": article.category.value if article.category else None,
                "importance_score": article.importance_score,
                "faithfulness_score": article.faithfulness_score,
                "created_at": article.created_at.isoformat() if article.created_at else None,
            },
            "chunks": len(chunks),
        },
        "audit_trail": [
            {
                "action": a.action,
                "actor": a.actor,
                "reasoning": a.reasoning,
                "timestamp": a.created_at.isoformat() if a.created_at else None,
            }
            for a in audits
        ],
        "explainability": article.explainability_log,
    }


async def get_newsletter_lineage(newsletter_id: str, db: AsyncSession) -> dict:
    """Full lineage for a newsletter."""
    result = await db.execute(select(Newsletter).where(Newsletter.id == newsletter_id))
    nl = result.scalar_one_or_none()
    if not nl:
        return {"error": "Newsletter not found"}

    article_ids = nl.article_ids or []

    return {
        "newsletter_id": newsletter_id,
        "title": nl.title,
        "status": nl.status.value if nl.status else None,
        "generated_at": nl.generated_at.isoformat() if nl.generated_at else None,
        "article_count": len(article_ids),
        "agent_pipeline": {
            "pm_agenda_summary": {
                "top_stories": len(nl.pm_agenda.get("top_stories", [])) if nl.pm_agenda else 0,
                "rejected": len(nl.pm_agenda.get("rejected", [])) if nl.pm_agenda else 0,
            },
            "designer_sections": len(nl.designer_blueprint.get("sections", [])) if nl.designer_blueprint else 0,
            "qa_approved": nl.qa_report.get("approved") if nl.qa_report else None,
            "faithfulness_score": nl.quality_metrics.get("faithfulness_score") if nl.quality_metrics else None,
            "qa_retries": nl.quality_metrics.get("qa_retries", 0) if nl.quality_metrics else 0,
        },
        "article_ids": article_ids,
    }
