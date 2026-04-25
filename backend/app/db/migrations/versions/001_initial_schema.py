"""Initial schema with pgvector

Revision ID: 001
Revises:
Create Date: 2026-04-26
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "sources",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(2048)),
        sa.Column("type", sa.Enum("website", "youtube", "newsletter", "arxiv", "upload", name="sourcetype"), nullable=False),
        sa.Column("active", sa.Boolean, default=True),
        sa.Column("fetch_config", sa.JSON, default={}),
        sa.Column("last_fetched_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "raw_content",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("source_id", UUID(as_uuid=False), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("url", sa.String(2048)),
        sa.Column("title", sa.String(1024)),
        sa.Column("raw_text", sa.Text),
        sa.Column("metadata", sa.JSON, default={}),
        sa.Column("scraped_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("processed", sa.Boolean, default=False),
    )

    op.create_table(
        "articles",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("raw_content_id", UUID(as_uuid=False), sa.ForeignKey("raw_content.id")),
        sa.Column("cluster_id", UUID(as_uuid=False), nullable=True),
        sa.Column("title", sa.String(1024)),
        sa.Column("summary", sa.Text),
        sa.Column("full_text", sa.Text),
        sa.Column("category", sa.Enum(
            "model_release", "eval_technique", "research_breakthrough",
            "tool_framework", "industry_news", "policy_safety", "tutorial_guide", "other",
            name="articlecategory"
        ), default="other"),
        sa.Column("subcategory", sa.String(255)),
        sa.Column("source_url", sa.String(2048)),
        sa.Column("published_at", sa.DateTime),
        sa.Column("importance_score", sa.Float, default=0.5),
        sa.Column("hallucination_score", sa.Float, default=0.0),
        sa.Column("faithfulness_score", sa.Float, default=1.0),
        sa.Column("explainability_log", sa.JSON, default={}),
        sa.Column("source_attribution", sa.JSON, default={}),
        sa.Column("embedding", Vector(768)),
        sa.Column("metadata", sa.JSON, default={}),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "clusters",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("label", sa.String(255)),
        sa.Column("centroid_embedding", Vector(768)),
        sa.Column("article_count", sa.Integer, default=0),
        sa.Column("representative_article_id", UUID(as_uuid=False), sa.ForeignKey("articles.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # Add FK from articles to clusters after both tables exist
    op.create_foreign_key("fk_articles_cluster", "articles", "clusters", ["cluster_id"], ["id"])

    op.create_table(
        "chunks",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("article_id", UUID(as_uuid=False), sa.ForeignKey("articles.id"), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", Vector(768)),
        sa.Column("chunk_index", sa.Integer, default=0),
        sa.Column("metadata", sa.JSON, default={}),
    )

    op.create_table(
        "newsletters",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("title", sa.String(512)),
        sa.Column("content", sa.JSON, default={}),
        sa.Column("pdf_path", sa.String(1024)),
        sa.Column("status", sa.Enum(
            "draft", "qa_review", "approved", "sent", "failed",
            name="newsletterstatus"
        ), default="draft"),
        sa.Column("pm_agenda", sa.JSON, default={}),
        sa.Column("designer_blueprint", sa.JSON, default={}),
        sa.Column("qa_report", sa.JSON, default={}),
        sa.Column("article_ids", sa.JSON, default=[]),
        sa.Column("quality_metrics", sa.JSON, default={}),
        sa.Column("generated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("entity_type", sa.String(100)),
        sa.Column("entity_id", sa.String(100)),
        sa.Column("action", sa.String(100)),
        sa.Column("actor", sa.String(100)),
        sa.Column("reasoning", sa.Text),
        sa.Column("input_snapshot", sa.JSON, default={}),
        sa.Column("output_snapshot", sa.JSON, default={}),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "eval_metrics",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("article_id", UUID(as_uuid=False), sa.ForeignKey("articles.id"), nullable=True),
        sa.Column("newsletter_id", UUID(as_uuid=False), sa.ForeignKey("newsletters.id"), nullable=True),
        sa.Column("run_id", sa.String(255)),
        sa.Column("metric_name", sa.String(255)),
        sa.Column("metric_value", sa.Float),
        sa.Column("details", sa.JSON, default={}),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # HNSW indexes for fast vector similarity search
    op.execute("CREATE INDEX ON articles USING hnsw (embedding vector_cosine_ops)")
    op.execute("CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops)")

    # Standard indexes
    op.create_index("ix_articles_category", "articles", ["category"])
    op.create_index("ix_articles_importance", "articles", ["importance_score"])
    op.create_index("ix_articles_cluster", "articles", ["cluster_id"])
    op.create_index("ix_raw_content_processed", "raw_content", ["processed"])
    op.create_index("ix_audit_log_actor", "audit_log", ["actor"])
    op.create_index("ix_audit_log_entity", "audit_log", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_table("eval_metrics")
    op.drop_table("audit_log")
    op.drop_table("newsletters")
    op.drop_table("chunks")
    op.drop_constraint("fk_articles_cluster", "articles")
    op.drop_table("clusters")
    op.drop_table("articles")
    op.drop_table("raw_content")
    op.drop_table("sources")
    op.execute("DROP EXTENSION IF EXISTS vector")
