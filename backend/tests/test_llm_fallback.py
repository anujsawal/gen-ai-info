"""
Unit tests for the Groq→Gemini fallback logic in app/core/llm.py.
No real API calls — everything is mocked.

Run with: cd backend && python -m pytest tests/test_llm_fallback.py -v
"""
import pytest
from unittest.mock import AsyncMock, patch
from langchain_core.messages import HumanMessage, AIMessage


@pytest.mark.asyncio
async def test_groq_rate_limit_triggers_gemini_fallback():
    """When Groq raises a rate-limit 429, Gemini must be called instead."""
    from app.core import llm as llm_mod

    groq_error = Exception("Rate limit reached: 429 tokens per day (TPD)")
    gemini_response = AIMessage(content="hello from gemini")

    with patch.object(llm_mod, "settings") as mock_settings, \
         patch("app.core.llm.ChatGroq") as mock_groq_cls, \
         patch("langchain_google_genai.ChatGoogleGenerativeAI") as mock_gemini_cls:

        mock_settings.groq_api_key = "fake_groq"
        mock_settings.gemini_api_key = "fake_gemini"
        mock_settings.llm_large = "llama-3.3-70b-versatile"
        mock_settings.gemini_model = "gemini-2.0-flash"

        mock_groq = AsyncMock()
        mock_groq.ainvoke.side_effect = groq_error
        mock_groq_cls.return_value = mock_groq

        mock_gemini = AsyncMock()
        mock_gemini.ainvoke.return_value = gemini_response
        mock_gemini_cls.return_value = mock_gemini

        result = await llm_mod.ainvoke_with_fallback([HumanMessage(content="test")])

    assert result == "hello from gemini"
    mock_groq.ainvoke.assert_called_once()
    mock_gemini.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_non_rate_limit_groq_error_does_not_fall_to_gemini():
    """A non-429 Groq error (e.g. auth failure) must propagate — not silently fall to Gemini."""
    from app.core import llm as llm_mod

    with patch.object(llm_mod, "settings") as mock_settings, \
         patch("app.core.llm.ChatGroq") as mock_groq_cls:

        mock_settings.groq_api_key = "fake_groq"
        mock_settings.gemini_api_key = ""
        mock_settings.llm_large = "llama-3.3-70b-versatile"

        mock_groq = AsyncMock()
        mock_groq.ainvoke.side_effect = Exception("Invalid API key — 401 Unauthorized")
        mock_groq_cls.return_value = mock_groq

        with pytest.raises(Exception, match="401"):
            await llm_mod.ainvoke_with_fallback([HumanMessage(content="test")])


@pytest.mark.asyncio
async def test_no_keys_raises_runtime_error():
    """If both Groq and Gemini keys are absent, a clear RuntimeError must be raised."""
    from app.core import llm as llm_mod

    with patch.object(llm_mod, "settings") as mock_settings:
        mock_settings.groq_api_key = ""
        mock_settings.gemini_api_key = ""
        mock_settings.llm_large = "llama-3.3-70b-versatile"

        with pytest.raises(RuntimeError, match="No LLM available"):
            await llm_mod.ainvoke_with_fallback([HumanMessage(content="test")])


@pytest.mark.asyncio
async def test_groq_success_does_not_call_gemini():
    """When Groq succeeds, Gemini must never be invoked."""
    from app.core import llm as llm_mod

    with patch.object(llm_mod, "settings") as mock_settings, \
         patch("app.core.llm.ChatGroq") as mock_groq_cls, \
         patch("langchain_google_genai.ChatGoogleGenerativeAI") as mock_gemini_cls:

        mock_settings.groq_api_key = "fake_groq"
        mock_settings.gemini_api_key = "fake_gemini"
        mock_settings.llm_large = "llama-3.3-70b-versatile"
        mock_settings.gemini_model = "gemini-2.0-flash"

        mock_groq = AsyncMock()
        mock_groq.ainvoke.return_value = AIMessage(content="groq response")
        mock_groq_cls.return_value = mock_groq

        mock_gemini = AsyncMock()
        mock_gemini_cls.return_value = mock_gemini

        result = await llm_mod.ainvoke_with_fallback([HumanMessage(content="test")])

    assert result == "groq response"
    mock_gemini.ainvoke.assert_not_called()
