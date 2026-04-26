"""
LLM provider with automatic fallback.

Primary: Groq (Llama 3.3 70B / 3.1 8B)
Fallback: Gemini 1.5 Flash — triggered when Groq returns a rate limit error (429).

Usage in agents:
    from app.core.llm import ainvoke_with_fallback
    raw = await ainvoke_with_fallback(messages, temperature=0.3)
"""
from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_RATE_LIMIT_SIGNALS = ("rate limit", "rate_limit", "429", "quota", "tokens per day", "tpd")


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(s in msg for s in _RATE_LIMIT_SIGNALS)


async def ainvoke_with_fallback(
    messages: list[BaseMessage],
    temperature: float = 0.3,
    model: str | None = None,
) -> str:
    """
    Invoke the LLM with Groq as primary and Gemini Flash as fallback.
    Returns the raw string content from the model response.
    """
    primary_model = model or settings.llm_large

    # Try Groq first
    if settings.groq_api_key:
        try:
            llm = ChatGroq(
                api_key=settings.groq_api_key,
                model=primary_model,
                temperature=temperature,
            )
            response = await llm.ainvoke(messages)
            return response.content
        except Exception as e:
            if _is_rate_limit(e):
                logger.warning("groq_rate_limited", model=primary_model, error=str(e)[:120])
            else:
                raise

    # Fallback: Gemini
    if settings.gemini_api_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            logger.info("llm_fallback_gemini", model=settings.gemini_model)
            gemini = ChatGoogleGenerativeAI(
                model=settings.gemini_model,
                google_api_key=settings.gemini_api_key,
                temperature=temperature,
            )
            response = await gemini.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.error("gemini_fallback_failed", error=str(e)[:200])
            raise

    raise RuntimeError(
        "No LLM available: Groq is rate-limited and GEMINI_API_KEY is not set. "
        "Add GEMINI_API_KEY to your environment variables."
    )
