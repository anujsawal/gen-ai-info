"""Add newsletter_feedback table

Revision ID: 002
Revises: 001
Create Date: 2026-04-26
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "newsletter_feedback",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("newsletter_id", UUID(as_uuid=False), sa.ForeignKey("newsletters.id"), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("routed_to", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_nf_newsletter_id", "newsletter_feedback", ["newsletter_id"])
    op.create_index("ix_nf_status", "newsletter_feedback", ["status"])
    op.execute(
        "CREATE INDEX ix_nf_embedding ON newsletter_feedback "
        "USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_table("newsletter_feedback")
