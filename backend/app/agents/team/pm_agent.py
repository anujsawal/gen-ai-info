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


SYSTEM_PROMPT = """You are the AI Curator / Editor-in-Chief of a Gen AI weekly digest newsletter.
Your job is to review clusters of AI articles and decide what to include, prioritize, and highlight.
You curate for a technical practitioner audience — engineers, researchers, and product builders.

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
4. Category balance — aim to cover multiple categories (research, tools, industry, policy)
5. Recency — prefer articles from the last 3 days

HARD RULES — these override all other criteria. Violations MUST go to rejected[]:

1. VENDOR CAP: Maximum 2 stories per company/vendor per edition.
   Vendors include: Anthropic, OpenAI, Google/DeepMind, Meta, Mistral, Cohere, xAI, Apple, Microsoft.
   If you have 3+ articles about the same vendor, keep the 2 most impactful and reject the rest.
   State the vendor name in reason_rejected (e.g. "Anthropic vendor cap — already have 2 Anthropic stories").

2. SOURCE DIVERSITY: The combined top_stories + deep_dive + quick_bites must represent
   at least 3 distinct sources. If the pool has fewer than 3 sources, note this in editorial_note.

3. NO MARKETING PAGES: Reject any article that is clearly a product landing page, pricing page,
   "supported countries" list, course catalog, or company help page. These have no news value.
   Signs: title contains "Learn", "Academy", "Supported Countries", "Pricing", "Get started".

4. NO DUPLICATES: If two clusters cover the same announcement or story, keep only the one with
   the higher cluster_size. Reject the duplicate with reason "duplicate of [other cluster_id]".

5. SUBSTANCE REQUIRED: Reject articles with fewer than 3 sentences of actual content.
   Short marketing blurbs, navigation pages, and error pages must be rejected.
"""


async def run_pm_agent(clusters: list[dict], user_feedback: list[str] | None = None) -> dict:
    """
    clusters: list of {cluster_id, representative_title, representative_summary,
                       category, cluster_size, article_ids}
    user_feedback: curated editorial feedback from previous newsletter editions
    Returns: agenda dict with top_stories, deep_dive, quick_bites, rejected
    """
    llm = _get_llm()
    cluster_text = json.dumps(clusters, indent=2, default=str)

    feedback_section = ""
    if user_feedback:
        feedback_section = (
            "\n\n### EDITORIAL FEEDBACK FROM PREVIOUS EDITIONS:\n"
            + "\n".join(f"- {f}" for f in user_feedback)
        )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Here are this week's article clusters:\n\n{cluster_text}{feedback_section}\n\nProduce the editorial agenda JSON.")
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
