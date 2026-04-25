"""
Newsletter Generation LangGraph Pipeline:
retrieval → pm_agent → designer_agent → developer_agent → qa_agent
                                              ↑___________|  (loop on rejection)
"""
from langgraph.graph import StateGraph, END
from typing import TypedDict, Any, Optional
import uuid
from datetime import datetime, timedelta
from sqlalchemy import select, desc, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.team.pm_agent import run_pm_agent
from app.agents.team.designer_agent import run_designer_agent
from app.agents.team.developer_agent import run_developer_agent
from app.agents.team.qa_agent import run_qa_agent
from app.db.models import Article, Cluster, Newsletter, NewsletterStatus, AuditLog
from app.agents.processing.embedder import embed_query
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class NewsletterState(TypedDict):
    db_session: Any
    lookback_days: int
    clusters: list[dict]            # enriched cluster data with articles
    cluster_articles: dict          # {cluster_id: article_data}
    pm_agenda: dict
    designer_blueprint: dict
    newsletter_content: dict
    qa_report: dict
    qa_retries: int
    newsletter_id: str
    errors: list[str]


async def retrieval_node(state: NewsletterState) -> NewsletterState:
    """Fetch recent clusters and their representative articles from DB."""
    db: AsyncSession = state["db_session"]
    lookback = timedelta(days=state.get("lookback_days", 7))
    since = datetime.utcnow() - lookback

    # Get recent articles — prefer published_at, fall back to created_at for sources without dates
    result = await db.execute(
        select(Article)
        .where(
            or_(
                Article.published_at >= since,
                and_(Article.published_at == None, Article.created_at >= since),
            )
        )
        .order_by(desc(Article.importance_score))
        .limit(settings.cluster_max_articles_per_run)
    )
    articles = result.scalars().all()

    # Group by cluster
    cluster_map: dict[str, list[Article]] = {}
    for article in articles:
        key = article.cluster_id or f"solo_{article.id}"
        cluster_map.setdefault(key, []).append(article)

    clusters = []
    cluster_articles = {}
    for cluster_key, arts in cluster_map.items():
        rep = max(arts, key=lambda a: a.importance_score or 0)
        clusters.append({
            "cluster_id": cluster_key,
            "representative_title": rep.title or "",
            "representative_summary": (rep.summary or rep.full_text or "")[:500],
            "category": rep.category.value if rep.category else "other",
            "cluster_size": len(arts),
            "article_ids": [a.id for a in arts],
        })
        cluster_articles[cluster_key] = {
            "title": rep.title,
            "full_text": rep.full_text or "",
            "source_url": rep.source_url,
            "category": rep.category.value if rep.category else "other",
            "source_attribution": rep.source_attribution,
        }

    logger.info("retrieval_done", clusters=len(clusters), articles=len(articles))
    return {**state, "clusters": clusters, "cluster_articles": cluster_articles}


async def pm_node(state: NewsletterState) -> NewsletterState:
    """Run PM Agent to prioritize and set editorial agenda."""
    agenda = await run_pm_agent(state["clusters"])

    # Log to audit
    db: AsyncSession = state["db_session"]
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        entity_type="newsletter",
        entity_id=state.get("newsletter_id", "pending"),
        action="pm_agenda_set",
        actor="pm_agent",
        reasoning=agenda.get("editorial_note", ""),
        input_snapshot={"cluster_count": len(state["clusters"])},
        output_snapshot={"top_stories": len(agenda.get("top_stories", [])),
                         "rejected": len(agenda.get("rejected", []))},
    ))
    await db.flush()

    return {**state, "pm_agenda": agenda}


async def designer_node(state: NewsletterState) -> NewsletterState:
    """Run Designer Agent to plan newsletter layout."""
    blueprint = await run_designer_agent(state["pm_agenda"], state["clusters"])

    db: AsyncSession = state["db_session"]
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        entity_type="newsletter",
        entity_id=state.get("newsletter_id", "pending"),
        action="designer_blueprint_created",
        actor="designer_agent",
        reasoning=blueprint.get("layout_rationale", ""),
        output_snapshot={"sections": len(blueprint.get("sections", []))},
    ))
    await db.flush()

    return {**state, "designer_blueprint": blueprint}


async def developer_node(state: NewsletterState) -> NewsletterState:
    """Run Developer Agent to write newsletter content."""
    qa_feedback = None
    if state.get("qa_report") and not state["qa_report"].get("approved", True):
        qa_feedback = state["qa_report"].get("improvement_suggestions", [])

    content = await run_developer_agent(
        state["designer_blueprint"],
        state["cluster_articles"],
        qa_feedback=qa_feedback,
    )
    return {**state, "newsletter_content": content}


async def qa_node(state: NewsletterState) -> NewsletterState:
    """Run QA Agent to evaluate content quality."""
    qa_report = await run_qa_agent(
        state["newsletter_content"],
        state["cluster_articles"],
    )
    retries = state.get("qa_retries", 0)
    return {**state, "qa_report": qa_report, "qa_retries": retries}


async def save_newsletter_node(state: NewsletterState) -> NewsletterState:
    """Save the approved newsletter to the database."""
    db: AsyncSession = state["db_session"]
    newsletter_id = str(uuid.uuid4())

    all_article_ids = []
    for cluster in state["clusters"]:
        all_article_ids.extend(cluster.get("article_ids", []))

    newsletter = Newsletter(
        id=newsletter_id,
        title=state["designer_blueprint"].get("newsletter_title", f"Gen AI Digest {datetime.utcnow().strftime('%b %d, %Y')}"),
        content=state["newsletter_content"],
        status=NewsletterStatus.approved,
        pm_agenda=state["pm_agenda"],
        designer_blueprint=state["designer_blueprint"],
        qa_report=state["qa_report"],
        article_ids=all_article_ids,
        quality_metrics={
            "faithfulness_score": state["qa_report"].get("overall_faithfulness_score"),
            "coverage_score": state["qa_report"].get("coverage_score"),
            "readability_score": state["qa_report"].get("readability_score"),
            "qa_retries": state.get("qa_retries", 0),
        },
    )
    db.add(newsletter)
    await db.commit()

    logger.info("newsletter_saved", id=newsletter_id)
    return {**state, "newsletter_id": newsletter_id}


def should_retry_or_finish(state: NewsletterState) -> str:
    """Route: if QA rejected and retries remain, go back to developer."""
    qa = state.get("qa_report", {})
    retries = state.get("qa_retries", 0)
    max_retries = settings.max_qa_retries

    if not qa.get("approved", True) and retries < max_retries:
        logger.info("qa_rejected_retrying", retry=retries + 1)
        # Increment retry counter
        state["qa_retries"] = retries + 1
        return "retry"
    return "save"


def build_newsletter_graph() -> StateGraph:
    g = StateGraph(NewsletterState)

    g.add_node("retrieval", retrieval_node)
    g.add_node("pm", pm_node)
    g.add_node("designer", designer_node)
    g.add_node("developer", developer_node)
    g.add_node("qa", qa_node)
    g.add_node("save", save_newsletter_node)

    g.set_entry_point("retrieval")
    g.add_edge("retrieval", "pm")
    g.add_edge("pm", "designer")
    g.add_edge("designer", "developer")
    g.add_edge("developer", "qa")
    g.add_conditional_edges("qa", should_retry_or_finish, {"retry": "developer", "save": "save"})
    g.add_edge("save", END)

    return g.compile()


newsletter_graph = build_newsletter_graph()
