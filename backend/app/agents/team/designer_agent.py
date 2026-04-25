"""
Designer Agent — Newsletter architecture.
Takes the PM agenda and designs the section layout,
tone, visual hierarchy, and formatting for each article.
"""
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.config import get_settings
from app.core.logging import get_logger
import json

logger = get_logger(__name__)
settings = get_settings()

_llm = None


def _get_llm() -> ChatGroq:
    global _llm
    if _llm is None:
        _llm = ChatGroq(
            api_key=settings.groq_api_key,
            model=settings.llm_fast,
            temperature=0.2,
        )
    return _llm


SYSTEM_PROMPT = """You are the Designer/Art Director of a Gen AI weekly digest newsletter.
Your job is to take an editorial agenda and design the newsletter layout.

Output valid JSON:
{
  "newsletter_title": "catchy title for this edition",
  "sections": [
    {
      "section_name": "string",
      "section_type": "executive_summary|top_stories|deep_dive|arxiv_highlights|quick_bites|qa_report|sources",
      "cluster_ids": ["string"],
      "format": "bullet_list|full_paragraph|card_grid|numbered_list",
      "tone": "formal|conversational|technical|engaging",
      "max_words_per_item": 150,
      "design_notes": "guidance for the Developer agent on how to write this section"
    }
  ],
  "layout_rationale": "1 paragraph explaining the layout decisions"
}

Design principles:
- Executive summary first (3-5 bullets, 30 words max each)
- Group stories by category in Top Stories
- Deep dive gets full treatment: context, technical details, implications
- ArXiv section: title, one-sentence abstract, why it matters
- Quick bites: one line each, punchy
- End with QA report showing quality metrics
- Keep total PDF to ~4 pages
"""


async def run_designer_agent(agenda: dict, clusters: list[dict]) -> dict:
    """
    agenda: output from pm_agent
    clusters: full cluster metadata for context
    Returns: blueprint dict with sections and layout
    """
    llm = _get_llm()

    context = {
        "agenda": agenda,
        "available_clusters": [{"id": c["cluster_id"], "title": c.get("representative_title"),
                                 "category": c.get("category")} for c in clusters],
    }

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Design the newsletter layout for this agenda:\n\n{json.dumps(context, indent=2)}\n\nOutput the blueprint JSON.")
    ]

    try:
        response = await llm.ainvoke(messages)
        raw = response.content.strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        blueprint = json.loads(raw)
        logger.info("designer_agent_done", sections=len(blueprint.get("sections", [])))
        return blueprint
    except Exception as e:
        logger.error("designer_agent_failed", error=str(e))
        # Fallback blueprint
        return {
            "newsletter_title": "Gen AI Digest",
            "sections": [
                {"section_name": "Executive Summary", "section_type": "executive_summary",
                 "cluster_ids": [], "format": "bullet_list", "tone": "engaging",
                 "max_words_per_item": 50, "design_notes": "Key takeaways"},
                {"section_name": "Top Stories", "section_type": "top_stories",
                 "cluster_ids": [s["cluster_id"] for s in agenda.get("top_stories", [])],
                 "format": "full_paragraph", "tone": "conversational",
                 "max_words_per_item": 150, "design_notes": "3-bullet summaries"},
            ],
            "layout_rationale": "Auto-generated fallback layout.",
        }
