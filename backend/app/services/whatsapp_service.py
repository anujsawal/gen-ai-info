"""
WhatsApp delivery via Twilio Sandbox.
Sends a PDF file to the configured WhatsApp number.
"""
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import os
import base64
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_client = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    return _client


async def send_pdf_to_whatsapp(pdf_path: str, caption: str = "Your Gen AI Digest is ready!") -> dict:
    """
    Send a PDF file to WhatsApp via Twilio.
    Note: Twilio WhatsApp requires the file to be publicly accessible.
    For development, we send the caption only and note the path.
    """
    if not os.path.exists(pdf_path):
        return {"success": False, "error": "PDF file not found"}

    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        logger.warning("twilio_not_configured")
        return {"success": False, "error": "Twilio not configured"}

    try:
        client = _get_client()
        file_size_kb = os.path.getsize(pdf_path) / 1024
        message_body = (
            f"{caption}\n\n"
            f"📄 Newsletter: {os.path.basename(pdf_path)}\n"
            f"📦 Size: {file_size_kb:.1f} KB\n\n"
            "Open the Gen AI Dashboard to view the full newsletter."
        )

        message = client.messages.create(
            body=message_body,
            from_=settings.twilio_whatsapp_from,
            to=settings.whatsapp_to,
        )

        logger.info("whatsapp_sent", message_sid=message.sid, pdf=pdf_path)
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
