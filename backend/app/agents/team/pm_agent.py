"""
PM Agent — Editorial prioritization.
Decides which clustered articles to include, ranks by importance,
and produces a structured newsletter agenda with full reasoning logged.
"""
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
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
            model=settings.llm_large,
            temperature=0.3,
        )
    return _llm


SYSTEM_PROMPT = """You are the PM (Product Manager / Editor-in-Chief) of a Gen AI weekly digest newsletter.
Your job is to review clusters of AI articles and decide what to include, prioritize, and highlight.

For each cluster, you receive:
- The representative article title and summary
- Number of sources covering it (cluster size)
- Article category

Your output must be valid JSON matching this schema:
{
  "top_stories": [
    {
      "cluster_id": "string",
      "reason_selected": "1-2 sentence explanation",
      "importance_score": 0.0-1.0,
      "recommended_format": "full_summary|brief|deep_dive"
    }
  ],
  "deep_dive": {"cluster_id": "string", "reason": "string"},
  "quick_bites": [{"cluster_id": "string", "reason_selected": "string"}],
  "rejected": [{"cluster_id": "string", "reason_rejected": "string"}],
  "executive_summary_bullets": ["bullet 1", "bullet 2", "bullet 3"],
  "editorial_note": "1 paragraph overall note on this week's AI news landscape"
}

Prioritization criteria (in order):
1. Novelty — genuinely new information, not a rehash
2. Impact — broad effect on the AI field or practitioners
3. Coverage breadth — more sources = more important
4. Category balance — aim to cover multiple categories
5. Recency — prefer articles from the last 3 days
"""


async def run_pm_agent(clusters: list[dict]) -> dict:
    """
    clusters: list of {cluster_id, representative_title, representative_summary,
                       category, cluster_size, article_ids}
    Returns: agenda dict with top_stories, deep_dive, quick_bites, rejected
    """
    llm = _get_llm()
    cluster_text = json.dumps(clusters, indent=2, default=str)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Here are this week's article clusters:\n\n{cluster_text}\n\nProduce the editorial agenda JSON.")
    ]

    try:
        response = await llm.ainvoke(messages)
        raw = response.content.strip()
        # Extract JSON if wrapped in markdown code block
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        agenda = json.loads(raw)
        logger.info("pm_agent_done",
                    top_stories=len(agenda.get("top_stories", [])),
                    rejected=len(agenda.get("rejected", [])))
        return agenda
    except Exception as e:
        logger.error("pm_agent_failed", error=str(e))
        # Fallback: include all clusters as top stories
        return {
            "top_stories": [{"cluster_id": c["cluster_id"], "reason_selected": "fallback",
                              "importance_score": 0.5, "recommended_format": "brief"} for c in clusters],
            "deep_dive": {"cluster_id": clusters[0]["cluster_id"], "reason": "fallback"} if clusters else None,
            "quick_bites": [],
            "rejected": [],
            "executive_summary_bullets": ["AI news this week"],
            "editorial_note": "Auto-generated due to PM agent error.",
        }
