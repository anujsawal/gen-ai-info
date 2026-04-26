from fastapi import APIRouter, Depends, BackgroundTasks, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.graph.ingestion_graph import ingestion_graph
from app.agents.processing.embedder import chunk_text, embed_texts
from app.agents.processing.cleaner import clean_text
from app.db.models import RawContent, Article, Chunk, Source, SourceType, AuditLog
import uuid
from datetime import datetime
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("/trigger")
async def trigger_ingestion(background_tasks: BackgroundTasks):
    """Trigger the full ingestion pipeline in the background."""
    from app.db.session import AsyncSessionLocal

    async def run():
        async with AsyncSessionLocal() as session:
            try:
                await ingestion_graph.ainvoke({
                    "sources": [], "raw_items": [], "clean_items": [],
                    "embedded_items": [], "cluster_map": {},
                    "stored_article_ids": [], "errors": [], "db_session": session,
                })
            except Exception as e:
                logger.error("ingestion_trigger_failed", error=str(e))

    background_tasks.add_task(run)
    return {"status": "ingestion_started", "message": "Pipeline running in background"}


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF/text document for RAG analysis and storage."""
    if not file.filename.endswith((".pdf", ".txt", ".md")):
        raise HTTPException(400, "Only PDF, TXT, and MD files supported")

    content = await file.read()

    if file.filename.endswith(".pdf"):
        import io
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            if not text.strip():
                raise HTTPException(400, "PDF appears to be image-only or has no extractable text")
        except ImportError:
            raise HTTPException(500, "pdfplumber not installed — contact admin")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"Could not read PDF: {str(e)}")
    else:
        text = content.decode("utf-8", errors="ignore")

    text = clean_text(text)
    if len(text.split()) < 50:
        raise HTTPException(400, "Document too short or unreadable")

    # Create a source record for the upload
    source = Source(
        id=str(uuid.uuid4()),
        name=file.filename,
        type=SourceType.upload,
        active=True,
    )
    db.add(source)

    raw = RawContent(
        id=str(uuid.uuid4()),
        source_id=source.id,
        title=file.filename,
        raw_text=text,
        scraped_at=datetime.utcnow(),
        processed=True,
        metadata={"filename": file.filename, "size_bytes": len(content)},
    )
    db.add(raw)
    await db.flush()

    # Embed and store
    embeddings = embed_texts([text])
    article = Article(
        id=str(uuid.uuid4()),
        raw_content_id=raw.id,
        title=file.filename,
        full_text=text,
        embedding=embeddings[0],
        source_attribution={"filename": file.filename, "type": "upload"},
    )
    db.add(article)
    await db.flush()

    chunks_text = chunk_text(text)
    if chunks_text:
        chunk_embeddings = embed_texts(chunks_text)
        for ci, (ct, ce) in enumerate(zip(chunks_text, chunk_embeddings)):
            db.add(Chunk(id=str(uuid.uuid4()), article_id=article.id,
                        content=ct, embedding=ce, chunk_index=ci))

    db.add(AuditLog(
        id=str(uuid.uuid4()), entity_type="article", entity_id=article.id,
        action="uploaded", actor="user_upload",
        reasoning=f"User uploaded file: {file.filename}",
    ))
    await db.commit()

    return {"article_id": article.id, "title": file.filename, "chunks": len(chunks_text)}
