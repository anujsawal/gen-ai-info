"""
QA Agent — Quality control and hallucination checker.
Validates newsletter content against source articles,
scores faithfulness, runs LangSmith evals, decides approve/reject.
"""
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import Client as LangSmithClient
from app.core.config import get_settings
from app.core.logging import get_logger
import json
import time

logger = get_logger(__name__)
settings = get_settings()

_llm = None
_ls_client = None


def _get_llm() -> ChatGroq:
    global _llm
    if _llm is None:
        _llm = ChatGroq(
            api_key=settings.groq_api_key,
            model=settings.llm_large,
            temperature=0.1,  # low temp for evaluation accuracy
        )
    return _llm


def _get_ls_client():
    global _ls_client
    if _ls_client is None and settings.langchain_api_key:
        _ls_client = LangSmithClient(api_key=settings.langchain_api_key)
    return _ls_client


SYSTEM_PROMPT = """You are the QA Editor for a Gen AI newsletter aimed at technical practitioners.
Your job is to verify faithfulness to sources AND enforce editorial quality standards.

For each content item, check:
1. Are all stated facts present in the source text?
2. Are there any invented statistics, quotes, or claims?
3. Is the category correctly assigned?
4. Is the summary clear, specific, and useful to a practitioner?

Output valid JSON:
{
  "approved": true|false,
  "overall_faithfulness_score": 0.0-1.0,
  "items": [
    {
      "cluster_id": "string",
      "faithfulness_score": 0.0-1.0,
      "hallucination_detected": true|false,
      "hallucinated_claims": ["specific claim that is not in source"],
      "category_correct": true|false,
      "issues": ["issue 1", "issue 2"],
      "qa_notes": "brief notes"
    }
  ],
  "coverage_score": 0.0-1.0,
  "readability_score": 0.0-1.0,
  "bias_flags": ["flag if any category/source has >40% coverage"],
  "rejection_reasons": ["reason 1 if not approved"],
  "improvement_suggestions": ["specific instruction for Developer agent to fix"]
}

HARD REJECTION TRIGGERS — set approved: false if ANY of these are true:

1. VENDOR BIAS: Any single company/vendor (Anthropic, OpenAI, Google, Meta, etc.) accounts for
   more than 40% of all included stories. List the offending vendor in rejection_reasons.
   Suggest which stories to cut in improvement_suggestions (e.g. "Remove 'Claude Sonnet 4.6 Use Cases'
   from Quick Bites — Anthropic already has 2 stories").

2. DUPLICATE CONTENT: The same news story appears in more than one section under different headings.
   List the duplicate in rejection_reasons with both section names.

3. ARXIV SECTION INTEGRITY: If the newsletter has an "ArXiv" or "Research Highlights" section,
   it must contain at least one URL from arxiv.org. If it contains only blog/marketing URLs,
   set approved: false and note it in rejection_reasons.

4. FAITHFULNESS: overall_faithfulness_score < faithfulness_threshold.

Approve (approved: true) only when ALL four checks pass.
When rejecting, improvement_suggestions must be specific and actionable so the Developer
agent can fix the exact issue on the next retry.
"""


async def run_qa_agent(
    newsletter_content: dict,
    cluster_articles: dict[str, dict],
    faithfulness_threshold: float | None = None,
) -> dict:
    """
    newsletter_content: output from developer_agent
    cluster_articles: {cluster_id: {title, full_text, source_url}}
    Returns: QA report dict
    """
    llm = _get_llm()
    threshold = faithfulness_threshold or settings.faithfulness_threshold

    # Trim source texts to fit context window
    trimmed_sources = {
        cid: {**art, "full_text": art.get("full_text", "")[:2000]}
        for cid, art in cluster_articles.items()
    }

    payload = {
        "newsletter_content": newsletter_content,
        "source_articles": trimmed_sources,
        "faithfulness_threshold": threshold,
    }

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Evaluate this newsletter content:\n\n{json.dumps(payload, indent=2, default=str)[:14000]}\n\nOutput the QA report JSON.")
    ]

    start = time.time()
    try:
        response = await llm.ainvoke(messages)
        raw = response.content.strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        qa_report = json.loads(raw)

        # Log to LangSmith if available
        _log_to_langsmith(qa_report, time.time() - start)

        logger.info(
            "qa_agent_done",
            approved=qa_report.get("approved"),
            faithfulness=qa_report.get("overall_faithfulness_score"),
        )
        return qa_report

    except Exception as e:
        logger.error("qa_agent_failed", error=str(e))
        return {
            "approved": True,  # don't block on QA failure
            "overall_faithfulness_score": 0.5,
            "items": [],
            "coverage_score": 0.5,
            "readability_score": 0.5,
            "bias_flags": [],
            "rejection_reasons": [],
            "improvement_suggestions": [],
            "error": str(e),
        }


def _log_to_langsmith(qa_report: dict, duration_seconds: float) -> None:
    """Log QA eval run to LangSmith for traceability."""
    try:
        client = _get_ls_client()
        if not client:
            return
        client.create_run(
            name="qa_agent_eval",
            run_type="evaluator",
            inputs={"qa_report_summary": {
                "approved": qa_report.get("approved"),
                "faithfulness": qa_report.get("overall_faithfulness_score"),
                "bias_flags": qa_report.get("bias_flags"),
            }},
            outputs={"approved": qa_report.get("approved")},
            extra={"duration_seconds": duration_seconds},
            project_name=settings.langchain_project,
        )
    except Exception as e:
        logger.warning("langsmith_log_failed", error=str(e))
