"""
WhatsApp delivery via Twilio Sandbox.
Sends a newsletter notification with PDF download link to WhatsApp.
"""
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import os
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_client = None

_BACKEND_URL = os.environ.get(
    "PUBLIC_API_URL",
    "https://gen-ai-info-production.up.railway.app",
)


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    return _client


async def send_pdf_to_whatsapp(
    pdf_path: str,
    caption: str = "Your Gen AI Digest is ready!",
    newsletter_id: str | None = None,
    summary_bullets: list[str] | None = None,
) -> dict:
    """
    Send a newsletter notification to WhatsApp with a PDF download link.
    Includes executive summary bullets and a direct PDF URL.
    """
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        logger.warning("twilio_not_configured")
        return {"success": False, "error": "Twilio not configured"}

    try:
        client = _get_client()

        # Build the message body
        lines = [f"📰 {caption}", ""]

        if summary_bullets:
            for bullet in summary_bullets[:4]:
                lines.append(f"• {bullet}")
            lines.append("")

        if newsletter_id:
            pdf_url = f"{_BACKEND_URL}/api/newsletter/{newsletter_id}/pdf"
            lines.append(f"📄 Download PDF:\n{pdf_url}")
        elif pdf_path and os.path.exists(pdf_path):
            file_size_kb = os.path.getsize(pdf_path) / 1024
            lines.append(f"📄 {os.path.basename(pdf_path)} ({file_size_kb:.0f} KB)")

        message_body = "\n".join(lines)

        message = client.messages.create(
            body=message_body,
            from_=settings.twilio_whatsapp_from,
            to=settings.whatsapp_to,
        )

        logger.info("whatsapp_sent", message_sid=message.sid, newsletter_id=newsletter_id)
        return {"success": True, "message_sid": message.sid}

    except TwilioRestException as e:
        logger.error("whatsapp_failed", error=str(e))
        return {"success": False, "error": str(e)}


async def send_text_to_whatsapp(text: str) -> dict:
    """Send a plain text message to WhatsApp."""
    if not settings.twilio_account_sid:
        return {"success": False, "error": "Twilio not configured"}
    try:
        client = _get_client()
        message = client.messages.create(
            body=text,
            from_=settings.twilio_whatsapp_from,
            to=settings.whatsapp_to,
        )
        return {"success": True, "message_sid": message.sid}
    except TwilioRestException as e:
        return {"success": False, "error": str(e)}
