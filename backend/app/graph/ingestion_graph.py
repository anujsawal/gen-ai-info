"""
Ingestion LangGraph Pipeline:
scraper_node → cleaner_node → embedder_node → clusterer_node → storage_node
"""
from langgraph.graph import StateGraph, END
from typing import TypedDict, Any
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
import functools
import yaml
import os
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

# Thread pool for CPU-bound work (embedding, clustering) so they don't block the event loop
_cpu_executor = ThreadPoolExecutor(max_workers=2)

from app.agents.scrapers.web_scraper import scrape_website_source
from app.agents.scrapers.youtube_agent import scrape_youtube_source
from app.agents.scrapers.newsletter_agent import scrape_newsletter_source
from app.agents.scrapers.arxiv_agent import scrape_arxiv_source
from app.agents.processing.cleaner import clean_raw_content, reset_dedup_cache
from app.agents.processing.embedder import embed_texts, chunk_text
from app.agents.processing.clusterer import cluster_articles, find_representative, compute_centroid
from app.db.models import Source, SourceType, RawContent, Article, Cluster, Chunk, AuditLog, ArticleCategory
from sqlalchemy import select as sa_select
from app.core.logging import get_logger

logger = get_logger(__name__)

SOURCES_CONFIG = os.path.join(os.path.dirname(__file__), "../../../config/sources.yaml")


class IngestionState(TypedDict):
    sources: list[dict]
    raw_items: list[dict]
    clean_items: list[dict]
    embedded_items: list[dict]
    cluster_map: dict[str, list[str]]  # cluster_key -> [item_index]
    stored_article_ids: list[str]
    errors: list[str]
    db_session: Any


def load_sources_config() -> dict:
    config_path = SOURCES_CONFIG
    if not os.path.exists(config_path):
        config_path = "config/sources.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


async def scraper_node(state: IngestionState) -> IngestionState:
    """Run all scrapers concurrently."""
    config = load_sources_config()
    tasks = []

    for source in config.get("websites", []):
        if source.get("active"):
            tasks.append(scrape_website_source(source))
    for source in config.get("youtube", []):
        if source.get("active"):
            tasks.append(scrape_youtube_source(source))
    for source in config.get("newsletters", []):
        if source.get("active"):
            tasks.append(scrape_newsletter_source(source))
    for source in config.get("arxiv", []):
        if source.get("active"):
            tasks.append(scrape_arxiv_source(source))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    raw_items = []
    errors = []
    for result in results:
        if isinstance(result, Exception):
            errors.append(str(result))
        elif isinstance(result, list):
            raw_items.extend(result)

    logger.info("scraper_node_done", total_items=len(raw_items), errors=len(errors))
    return {**state, "raw_items": raw_items, "errors": errors}


async def cleaner_node(state: IngestionState) -> IngestionState:
    """Clean and deduplicate raw items."""
    reset_dedup_cache()
    clean_items = []
    for item in state["raw_items"]:
        cleaned = clean_raw_content(item)
        if cleaned:
            clean_items.append(cleaned)
    logger.info("cleaner_node_done", kept=len(clean_items), dropped=len(state["raw_items"]) - len(clean_items))
    return {**state, "clean_items": clean_items}


async def embedder_node(state: IngestionState) -> IngestionState:
    """Embed all clean items — runs sentence-transformers in a thread pool."""
    texts = [item["raw_text"] for item in state["clean_items"]]
    if not texts:
        return {**state, "embedded_items": []}

    loop = asyncio.get_event_loop()
    embeddings = await loop.run_in_executor(_cpu_executor, embed_texts, texts)

    embedded_items = [{**item, "embedding": emb} for item, emb in zip(state["clean_items"], embeddings)]
    logger.info("embedder_node_done", count=len(embedded_items))
    return {**state, "embedded_items": embedded_items}


async def clusterer_node(state: IngestionState) -> IngestionState:
    """Cluster embedded items — runs HDBSCAN in a thread pool."""
    items = state["embedded_items"]
    if not items:
        return {**state, "cluster_map": {}}

    embeddings = [item["embedding"] for item in items]
    indices = [str(i) for i in range(len(items))]

    loop = asyncio.get_event_loop()
    cluster_map = await loop.run_in_executor(
        _cpu_executor, functools.partial(cluster_articles, embeddings, indices)
    )

    logger.info("clusterer_node_done", clusters=len(cluster_map))
    return {**state, "cluster_map": cluster_map}


async def storage_node(state: IngestionState) -> IngestionState:
    """Persist all items in three bulk flushes instead of per-row round-trips."""
    db: AsyncSession = state["db_session"]
    items = state["embedded_items"]
    cluster_map = state["cluster_map"]

    if not items:
        return {**state, "stored_article_ids": []}

    # ── 1. Reverse index: item_index_str → cluster_key ─────────────────────
    index_to_cluster: dict[str, str] = {
        idx: key for key, indices in cluster_map.items() for idx in indices
    }

    # ── 2. Bulk-insert cluster records (one flush) ──────────────────────────
    cluster_db_ids: dict[str, str] = {}
    for cluster_key, indices in cluster_map.items():
        cluster_embeddings = [items[int(i)]["embedding"] for i in indices]
        cluster = Cluster(
            id=str(uuid.uuid4()),
            label=cluster_key,
            centroid_embedding=compute_centroid(cluster_embeddings),
            article_count=len(indices),
        )
        db.add(cluster)
        cluster_db_ids[cluster_key] = cluster.id

    await db.flush()  # flush 1: get cluster PKs

    # ── 2.5. Look up or create Source records ──────────────────────────────
    def _infer_source_type(item: dict) -> SourceType:
        scraper = item.get("metadata", {}).get("scraper", "")
        if scraper == "arxiv":
            return SourceType.arxiv
        if scraper in ("youtube_transcript", "youtube"):
            return SourceType.youtube
        if scraper in ("rss", "newsletter"):
            return SourceType.newsletter
        return SourceType.website

    unique_source_names: dict[str, dict] = {}
    for item in items:
        name = item.get("source_name") or "unknown"
        if name not in unique_source_names:
            unique_source_names[name] = item

    existing_sources = (await db.execute(
        sa_select(Source).where(Source.name.in_(unique_source_names.keys()))
    )).scalars().all()
    source_name_to_id: dict[str, str] = {s.name: s.id for s in existing_sources}

    for name, item in unique_source_names.items():
        if name not in source_name_to_id:
            new_src = Source(
                id=str(uuid.uuid4()),
                name=name,
                type=_infer_source_type(item),
                active=True,
            )
            db.add(new_src)
            source_name_to_id[name] = new_src.id

    await db.flush()  # flush 1b: get source PKs

    # ── 3. Bulk-insert RawContent + Article rows (one flush each) ───────────
    raw_objects: list[RawContent] = []
    now = datetime.utcnow()
    for item in items:
        raw = RawContent(
            id=str(uuid.uuid4()),
            source_id=source_name_to_id.get(item.get("source_name") or "unknown"),
            url=item.get("url", ""),
            title=item.get("title", ""),
            raw_text=item.get("raw_text", ""),
            metadata=item.get("metadata", {}),
            scraped_at=now,
            processed=True,
        )
        db.add(raw)
        raw_objects.append(raw)

    await db.flush()  # flush 2: get raw PKs

    article_objects: list[Article] = []
    for idx, (item, raw) in enumerate(zip(items, raw_objects)):
        cluster_key = index_to_cluster.get(str(idx))
        article = Article(
            id=str(uuid.uuid4()),
            raw_content_id=raw.id,
            cluster_id=cluster_db_ids.get(cluster_key) if cluster_key else None,
            title=item.get("title", ""),
            full_text=item.get("raw_text", ""),
            source_url=item.get("url", ""),
            published_at=item.get("published_at"),
            embedding=item["embedding"],
            source_attribution={"original_url": item.get("url"), "source_name": item.get("source_name")},
            metadata=item.get("metadata", {}),
        )
        db.add(article)
        article_objects.append(article)

    await db.flush()  # flush 3: get article PKs

    # ── 4. Chunk all articles, embed in ONE batch call, bulk-insert ─────────
    all_chunk_texts: list[str] = []
    chunk_meta: list[tuple[str, int]] = []  # (article_id, chunk_index)

    for article, item in zip(article_objects, items):
        for ci, ct in enumerate(chunk_text(item.get("raw_text", ""))):
            all_chunk_texts.append(ct)
            chunk_meta.append((article.id, ci))

    if all_chunk_texts:
        chunk_embeddings = embed_texts(all_chunk_texts)  # single batch call
        for (art_id, ci), content, emb in zip(chunk_meta, all_chunk_texts, chunk_embeddings):
            db.add(Chunk(id=str(uuid.uuid4()), article_id=art_id,
                         content=content, embedding=emb, chunk_index=ci))

    # ── 5. Bulk-insert audit log entries ────────────────────────────────────
    for idx, (article, item) in enumerate(zip(article_objects, items)):
        cluster_key = index_to_cluster.get(str(idx))
        db.add(AuditLog(
            id=str(uuid.uuid4()),
            entity_type="article",
            entity_id=article.id,
            action="ingested",
            actor="ingestion_graph",
            reasoning=f"Scraped from {item.get('source_name')}, cluster {cluster_key}",
            output_snapshot={"title": item.get("title"), "cluster": cluster_key},
        ))

    await db.commit()
    stored_ids = [a.id for a in article_objects]
    logger.info("storage_node_done", stored=len(stored_ids),
                chunks=len(all_chunk_texts), clusters=len(cluster_db_ids))
    return {**state, "stored_article_ids": stored_ids}


def build_ingestion_graph() -> StateGraph:
    g = StateGraph(IngestionState)
    g.add_node("scraper", scraper_node)
    g.add_node("cleaner", cleaner_node)
    g.add_node("embedder", embedder_node)
    g.add_node("clusterer", clusterer_node)
    g.add_node("storage", storage_node)

    g.set_entry_point("scraper")
    g.add_edge("scraper", "cleaner")
    g.add_edge("cleaner", "embedder")
    g.add_edge("embedder", "clusterer")
    g.add_edge("clusterer", "storage")
    g.add_edge("storage", END)

    return g.compile()


ingestion_graph = build_ingestion_graph()
