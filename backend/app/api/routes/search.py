from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.session import get_db
from app.agents.processing.embedder import embed_query
from app.core.config import get_settings

router = APIRouter(prefix="/search", tags=["search"])
settings = get_settings()


@router.get("")
async def semantic_search(
    q: str = Query(..., min_length=3),
    limit: int = Query(10, ge=1, le=50),
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """RAG semantic search over article chunks using pgvector."""
    query_embedding = embed_query(q)
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    category_filter = "AND a.category = :category" if category else ""

    sql = text(f"""
        SELECT
            c.content,
            c.chunk_index,
            a.id AS article_id,
            a.title,
            a.source_url,
            a.category,
            a.importance_score,
            a.faithfulness_score,
            a.source_attribution,
            1 - (c.embedding <=> CAST(:embedding AS vector)) AS similarity_score
        FROM chunks c
        JOIN articles a ON c.article_id = a.id
        WHERE 1=1 {category_filter}
        ORDER BY c.embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
    """)

    params = {"embedding": embedding_str, "limit": limit}
    if category:
        params["category"] = category

    result = await db.execute(sql, params)
    rows = result.fetchall()

    return {
        "query": q,
        "results": [
            {
                "article_id": row.article_id,
                "title": row.title,
                "excerpt": row.content[:300],
                "source_url": row.source_url,
                "category": row.category,
                "importance_score": row.importance_score,
                "faithfulness_score": row.faithfulness_score,
                "similarity_score": round(float(row.similarity_score), 3),
                "source": row.source_attribution,
            }
            for row in rows
        ],
    }
