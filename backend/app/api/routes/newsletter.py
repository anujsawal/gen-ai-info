from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.session import get_db
from app.db.models import Newsletter
from app.graph.newsletter_graph import newsletter_graph
from app.services.pdf_service import generate_pdf
from app.services.whatsapp_service import send_pdf_to_whatsapp
from app.core.logging import get_logger
import os

logger = get_logger(__name__)
router = APIRouter(prefix="/newsletter", tags=["newsletter"])


@router.post("/generate")
async def generate_newsletter(lookback_days: int = 7, db: AsyncSession = Depends(get_db)):
    """Generate a newsletter from recent articles."""
    try:
        result = await newsletter_graph.ainvoke({
            "db_session": db,
            "lookback_days": lookback_days,
            "clusters": [], "cluster_articles": {},
            "pm_agenda": {}, "designer_blueprint": {},
            "newsletter_content": {}, "qa_report": {},
            "qa_retries": 0, "newsletter_id": "", "errors": [],
        })
        newsletter_id = result.get("newsletter_id", "")
        if not newsletter_id:
            raise HTTPException(500, "Newsletter generation failed — no ID returned")

        content = result.get("newsletter_content", {})
        qa = result.get("qa_report", {})
        pdf_path = await generate_pdf(newsletter_id, content, qa)

        # Update newsletter with PDF path
        nl_result = await db.execute(select(Newsletter).where(Newsletter.id == newsletter_id))
        nl = nl_result.scalar_one_or_none()
        if nl and pdf_path:
            nl.pdf_path = pdf_path
            await db.commit()

        return {
            "newsletter_id": newsletter_id,
            "pdf_path": pdf_path,
            "qa_approved": qa.get("approved"),
            "faithfulness_score": qa.get("overall_faithfulness_score"),
        }
    except Exception as e:
        logger.error("generate_newsletter_failed", error=str(e))
        raise HTTPException(500, str(e))


@router.post("/send/{newsletter_id}")
async def send_newsletter(newsletter_id: str, db: AsyncSession = Depends(get_db)):
    """Send an existing newsletter to WhatsApp with PDF download link."""
    result = await db.execute(select(Newsletter).where(Newsletter.id == newsletter_id))
    nl = result.scalar_one_or_none()
    if not nl:
        raise HTTPException(404, "Newsletter not found")

    summary_bullets = (nl.content or {}).get("executive_summary", []) if nl.content else []

    send_result = await send_pdf_to_whatsapp(
        pdf_path=nl.pdf_path or "",
        caption=nl.title or "Your Gen AI Digest is ready!",
        newsletter_id=newsletter_id,
        summary_bullets=summary_bullets,
    )
    if send_result["success"]:
        from datetime import datetime
        nl.sent_at = datetime.utcnow()
        await db.commit()
    return send_result


@router.post("/generate-and-send")
async def generate_and_send(lookback_days: int = 7, db: AsyncSession = Depends(get_db)):
    """Generate and immediately send newsletter to WhatsApp."""
    gen_result = await generate_newsletter(lookback_days=lookback_days, db=db)
    send_result = await send_newsletter(newsletter_id=gen_result["newsletter_id"], db=db)
    return {**gen_result, "whatsapp": send_result}


@router.get("/list")
async def list_newsletters(limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Newsletter).order_by(desc(Newsletter.generated_at)).limit(limit)
    )
    newsletters = result.scalars().all()
    return [
        {
            "id": nl.id, "title": nl.title, "status": nl.status.value if nl.status else None,
            "generated_at": nl.generated_at.isoformat() if nl.generated_at else None,
            "sent_at": nl.sent_at.isoformat() if nl.sent_at else None,
            "faithfulness_score": nl.quality_metrics.get("faithfulness_score") if nl.quality_metrics else None,
        }
        for nl in newsletters
    ]


@router.get("/{newsletter_id}")
async def get_newsletter(newsletter_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Newsletter).where(Newsletter.id == newsletter_id))
    nl = result.scalar_one_or_none()
    if not nl:
        raise HTTPException(404, "Newsletter not found")
    return {
        "id": nl.id, "title": nl.title,
        "content": nl.content,
        "pm_agenda": nl.pm_agenda,
        "designer_blueprint": nl.designer_blueprint,
        "qa_report": nl.qa_report,
        "quality_metrics": nl.quality_metrics,
        "status": nl.status.value if nl.status else None,
        "generated_at": nl.generated_at.isoformat() if nl.generated_at else None,
    }


@router.get("/{newsletter_id}/pdf")
async def download_newsletter_pdf(newsletter_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Newsletter).where(Newsletter.id == newsletter_id))
    nl = result.scalar_one_or_none()
    if not nl:
        raise HTTPException(404, "Newsletter not found")

    # Regenerate if file is missing (Railway has ephemeral storage; files are lost on redeploy)
    if not nl.pdf_path or not os.path.exists(nl.pdf_path):
        pdf_path = await generate_pdf(newsletter_id, nl.content or {}, nl.qa_report or {})
        if not pdf_path or not os.path.exists(pdf_path):
            raise HTTPException(500, "Could not generate PDF")
        nl.pdf_path = pdf_path
        await db.commit()

    return FileResponse(nl.pdf_path, media_type="application/pdf", filename=os.path.basename(nl.pdf_path))
