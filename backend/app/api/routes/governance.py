from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from app.db.session import get_db
from app.db.models import AuditLog, Article, EvalMetric, Newsletter
from app.governance.lineage_tracker import get_article_lineage, get_newsletter_lineage
from app.governance.responsible_ai import run_responsible_ai_checks

router = APIRouter(prefix="/governance", tags=["governance"])


@router.get("/lineage/article/{article_id}")
async def article_lineage(article_id: str, db: AsyncSession = Depends(get_db)):
    return await get_article_lineage(article_id, db)


@router.get("/lineage/newsletter/{newsletter_id}")
async def newsletter_lineage(newsletter_id: str, db: AsyncSession = Depends(get_db)):
    return await get_newsletter_lineage(newsletter_id, db)


@router.get("/audit-log")
async def get_audit_log(
    actor: str | None = None,
    entity_type: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    query = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
    if actor:
        query = query.where(AuditLog.actor == actor)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)

    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        {
            "id": log.id,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "action": log.action,
            "actor": log.actor,
            "reasoning": log.reasoning,
            "timestamp": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


@router.get("/metrics/summary")
async def governance_metrics(db: AsyncSession = Depends(get_db)):
    """Aggregate quality metrics across all articles and newsletters."""
    article_stats = await db.execute(
        select(
            func.avg(Article.faithfulness_score).label("avg_faithfulness"),
            func.avg(Article.importance_score).label("avg_importance"),
            func.avg(Article.hallucination_score).label("avg_hallucination"),
            func.count(Article.id).label("total_articles"),
        )
    )
    row = article_stats.one()

    newsletter_stats = await db.execute(
        select(func.count(Newsletter.id).label("total_newsletters"))
    )
    nl_row = newsletter_stats.one()

    audit_by_actor = await db.execute(
        select(AuditLog.actor, func.count(AuditLog.id).label("count"))
        .group_by(AuditLog.actor)
    )

    return {
        "articles": {
            "total": row.total_articles,
            "avg_faithfulness_score": round(float(row.avg_faithfulness or 0), 3),
            "avg_importance_score": round(float(row.avg_importance or 0), 3),
            "avg_hallucination_score": round(float(row.avg_hallucination or 0), 3),
        },
        "newsletters": {"total": nl_row.total_newsletters},
        "agent_activity": {r.actor: r.count for r in audit_by_actor},
    }


@router.get("/responsible-ai/check")
async def responsible_ai_check(limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Run responsible AI checks on recent articles."""
    result = await db.execute(
        select(Article).order_by(desc(Article.created_at)).limit(limit)
    )
    articles = result.scalars().all()
    article_dicts = [
        {"raw_text": a.full_text or "", "source_name": a.source_attribution.get("source_name", "") if a.source_attribution else ""}
        for a in articles
    ]
    return run_responsible_ai_checks(article_dicts)
