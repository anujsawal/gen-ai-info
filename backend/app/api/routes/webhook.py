from fastapi import APIRouter, Request, Form
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    Body: str = Form(default=""),
    From: str = Form(default=""),
    NumMedia: str = Form(default="0"),
    MediaUrl0: str = Form(default=""),
    MediaContentType0: str = Form(default=""),
):
    """Handle inbound WhatsApp messages from Twilio."""
    logger.info("whatsapp_inbound", from_=From, body=Body)
    body_lower = Body.lower().strip()

    if any(cmd in body_lower for cmd in ["send report", "newsletter", "digest"]):
        from app.db.session import AsyncSessionLocal
        from app.graph.newsletter_graph import newsletter_graph
        from app.services.pdf_service import generate_pdf
        from app.services.whatsapp_service import send_pdf_to_whatsapp

        async with AsyncSessionLocal() as db:
            result = await newsletter_graph.ainvoke({
                "db_session": db, "lookback_days": 7,
                "clusters": [], "cluster_articles": {},
                "pm_agenda": {}, "designer_blueprint": {},
                "newsletter_content": {}, "qa_report": {},
                "qa_retries": 0, "newsletter_id": "", "errors": [],
            })
        newsletter_id = result.get("newsletter_id", "")
        if newsletter_id:
            pdf_path = await generate_pdf(newsletter_id, result.get("newsletter_content", {}), result.get("qa_report", {}))
            if pdf_path:
                await send_pdf_to_whatsapp(pdf_path, "📰 Your Gen AI Digest — on demand!")

    elif "help" in body_lower:
        from app.services.whatsapp_service import send_text_to_whatsapp
        await send_text_to_whatsapp(
            "Gen AI Info Bot commands:\n"
            "• 'send report' — generate and send newsletter now\n"
            "• 'newsletter' — same as above\n"
            "• Send a PDF — I'll analyze it and send back a summary"
        )

    # Twilio expects an empty 200 response
    return ""
