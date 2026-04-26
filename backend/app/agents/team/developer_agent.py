"""
Developer Agent — Content writer.
Takes the Designer blueprint and writes all newsletter content:
headlines, 3-bullet summaries, deep-dive prose, transitions.
"""
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.llm import ainvoke_with_fallback
import json

logger = get_logger(__name__)
settings = get_settings()


SYSTEM_PROMPT = """You are the Content Writer / Developer for a Gen AI newsletter.
Your job is to write high-quality newsletter content based on the Designer's blueprint and source articles.

For each section in the blueprint, write the content. Output valid JSON:
{
  "sections": [
    {
      "section_name": "string",
      "section_type": "string",
      "content": [
        {
          "cluster_id": "string",
          "headline": "catchy one-line headline",
          "summary_bullets": ["bullet 1", "bullet 2", "bullet 3"],
          "key_insight": "the single most important takeaway in one sentence",
          "body": "full paragraph(s) if format requires it",
          "source_url": "original source URL",
          "category": "string"
        }
      ]
    }
  ],
  "executive_summary": ["bullet 1", "bullet 2", "bullet 3", "bullet 4", "bullet 5"]
}

Rules:
- Bullets must be factual and grounded in the source text provided
- Do NOT invent facts, statistics, or quotes
- Keep bullets under 25 words each
- Deep dive sections can be up to 300 words
- Always include source attribution
- Mark any uncertain claims with [unverified]
"""


async def run_developer_agent(
    blueprint: dict,
    cluster_articles: dict[str, dict],  # {cluster_id: article_data}
    qa_feedback: list[str] | None = None,
    user_feedback: list[str] | None = None,
) -> dict:
    """
    blueprint: output from designer_agent
    cluster_articles: {cluster_id: {title, full_text, source_url, category}}
    qa_feedback: list of issues from a previous QA rejection (for re-runs)
    user_feedback: curated writing/style feedback from previous newsletter editions
    Returns: newsletter content dict
    """
    feedback_text = ""
    if qa_feedback:
        feedback_text = f"\n\nQA FEEDBACK TO FIX:\n" + "\n".join(f"- {f}" for f in qa_feedback)

    user_feedback_section = ""
    if user_feedback:
        user_feedback_section = (
            "\n\nUSER FEEDBACK ON WRITING STYLE:\n"
            + "\n".join(f"- {f}" for f in user_feedback)
        )

    payload = {
        "blueprint": blueprint,
        "source_articles": cluster_articles,
    }

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Write the newsletter content for this blueprint and source articles:\n\n{json.dumps(payload, indent=2, default=str)[:12000]}{feedback_text}{user_feedback_section}\n\nOutput the content JSON.")
    ]

    try:
        raw = (await ainvoke_with_fallback(messages, temperature=0.4)).strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        content = json.loads(raw)
        logger.info("developer_agent_done", sections=len(content.get("sections", [])))
        return content
    except Exception as e:
        logger.error("developer_agent_failed", error=str(e))
        # Return minimal fallback
        return {
            "sections": [],
            "executive_summary": ["AI news this week — see sources for details."],
        }
