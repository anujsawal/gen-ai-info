import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, String, Boolean, Float, Integer, Text, DateTime,
    ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from pgvector.sqlalchemy import Vector
import enum


class Base(DeclarativeBase):
    pass


class SourceType(str, enum.Enum):
    website = "website"
    youtube = "youtube"
    newsletter = "newsletter"
    arxiv = "arxiv"
    upload = "upload"


class ArticleCategory(str, enum.Enum):
    model_release = "model_release"
    eval_technique = "eval_technique"
    research_breakthrough = "research_breakthrough"
    tool_framework = "tool_framework"
    industry_news = "industry_news"
    policy_safety = "policy_safety"
    tutorial_guide = "tutorial_guide"
    other = "other"


class NewsletterStatus(str, enum.Enum):
    draft = "draft"
    qa_review = "qa_review"
    approved = "approved"
    sent = "sent"
    failed = "failed"


def _uuid():
    return str(uuid.uuid4())


class Source(Base):
    __tablename__ = "sources"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)
    url = Column(String(2048))
    type = Column(SAEnum(SourceType), nullable=False)
    active = Column(Boolean, default=True)
    fetch_config = Column(JSON, default=dict)
    last_fetched_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    raw_contents = relationship("RawContent", back_populates="source")


class RawContent(Base):
    __tablename__ = "raw_content"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    source_id = Column(UUID(as_uuid=False), ForeignKey("sources.id"), nullable=False)
    url = Column(String(2048))
    title = Column(String(1024))
    raw_text = Column(Text)
    extra = Column("metadata", JSON, default=dict)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    processed = Column(Boolean, default=False)

    source = relationship("Source", back_populates="raw_contents")
    article = relationship("Article", back_populates="raw_content", uselist=False)


class Cluster(Base):
    __tablename__ = "clusters"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    label = Column(String(255))
    centroid_embedding = Column(Vector(768))
    article_count = Column(Integer, default=0)
    representative_article_id = Column(UUID(as_uuid=False), ForeignKey("articles.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    articles = relationship("Article", back_populates="cluster", foreign_keys="[Article.cluster_id]")


class Article(Base):
    __tablename__ = "articles"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    raw_content_id = Column(UUID(as_uuid=False), ForeignKey("raw_content.id"))
    cluster_id = Column(UUID(as_uuid=False), ForeignKey("clusters.id"), nullable=True)
    title = Column(String(1024))
    summary = Column(Text)
    full_text = Column(Text)
    category = Column(SAEnum(ArticleCategory), default=ArticleCategory.other)
    subcategory = Column(String(255))
    source_url = Column(String(2048))
    published_at = Column(DateTime)
    importance_score = Column(Float, default=0.5)       # PM agent score 0-1
    hallucination_score = Column(Float, default=0.0)    # QA agent score 0-1
    faithfulness_score = Column(Float, default=1.0)     # summary vs source 0-1
    explainability_log = Column(JSON, default=dict)     # agent reasoning
    source_attribution = Column(JSON, default=dict)     # original source refs
    embedding = Column(Vector(768))
    extra = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    raw_content = relationship("RawContent", back_populates="article")
    cluster = relationship("Cluster", back_populates="articles", foreign_keys=[cluster_id])
    chunks = relationship("Chunk", back_populates="article")
    eval_metrics = relationship("EvalMetric", back_populates="article")


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    article_id = Column(UUID(as_uuid=False), ForeignKey("articles.id"), nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(768))
    chunk_index = Column(Integer, default=0)
    extra = Column("metadata", JSON, default=dict)

    article = relationship("Article", back_populates="chunks")


class Newsletter(Base):
    __tablename__ = "newsletters"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    title = Column(String(512))
    content = Column(JSON, default=dict)         # structured newsletter content
    pdf_path = Column(String(1024))
    status = Column(SAEnum(NewsletterStatus), default=NewsletterStatus.draft)
    pm_agenda = Column(JSON, default=dict)       # PM agent editorial decisions
    designer_blueprint = Column(JSON, default=dict)  # Designer layout plan
    qa_report = Column(JSON, default=dict)       # QA agent evaluation
    article_ids = Column(JSON, default=list)
    quality_metrics = Column(JSON, default=dict)
    generated_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime)

    eval_metrics = relationship("EvalMetric", back_populates="newsletter")


class AuditLog(Base):
    """Governance audit trail — every agent action logged here."""
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    entity_type = Column(String(100))   # article, newsletter, source, chunk
    entity_id = Column(String(100))
    action = Column(String(100))        # created, updated, classified, summarized, etc.
    actor = Column(String(100))         # pm_agent, designer_agent, developer_agent, qa_agent, scraper
    reasoning = Column(Text)            # WHY the agent did this (explainability)
    input_snapshot = Column(JSON, default=dict)
    output_snapshot = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class EvalMetric(Base):
    """LangSmith + custom quality metrics per article/newsletter run."""
    __tablename__ = "eval_metrics"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    article_id = Column(UUID(as_uuid=False), ForeignKey("articles.id"), nullable=True)
    newsletter_id = Column(UUID(as_uuid=False), ForeignKey("newsletters.id"), nullable=True)
    run_id = Column(String(255))   # LangSmith run ID
    metric_name = Column(String(255))
    metric_value = Column(Float)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    article = relationship("Article", back_populates="eval_metrics")
    newsletter = relationship("Newsletter", back_populates="eval_metrics")
