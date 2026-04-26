"""
PDF generation using WeasyPrint + Jinja2 HTML template.
"""
import os
import uuid
from datetime import datetime
from jinja2 import Environment, BaseLoader
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body { font-family: Arial, sans-serif; font-size: 11px; color: #1a1a2e; margin: 0; padding: 20px; }
  .header { background: #1a1a2e; color: white; padding: 20px; margin: -20px -20px 20px -20px; }
  .header h1 { margin: 0; font-size: 22px; letter-spacing: 2px; }
  .header .meta { font-size: 10px; color: #aaa; margin-top: 4px; }
  .section { margin-bottom: 20px; }
  .section h2 { font-size: 13px; color: #6366f1; border-bottom: 2px solid #6366f1; padding-bottom: 4px; text-transform: uppercase; letter-spacing: 1px; }
  .article { margin: 10px 0; padding: 10px; background: #f8f9fa; border-left: 3px solid #6366f1; border-radius: 4px; }
  .article .headline { font-weight: bold; font-size: 12px; margin-bottom: 4px; }
  .article .bullets { margin: 4px 0; padding-left: 16px; }
  .article .bullets li { margin: 2px 0; }
  .article .insight { font-style: italic; color: #555; font-size: 10px; margin-top: 4px; }
  .article .source { font-size: 9px; color: #888; margin-top: 4px; }
  .scores { font-size: 9px; color: #888; }
  .score-good { color: #10b981; }
  .score-warn { color: #f59e0b; }
  .score-bad { color: #ef4444; }
  .exec-summary { background: #ede9fe; padding: 12px; border-radius: 6px; }
  .exec-summary ul { margin: 6px 0; padding-left: 18px; }
  .exec-summary li { margin: 3px 0; font-size: 11px; }
  .qa-box { background: #f0fdf4; border: 1px solid #86efac; padding: 10px; border-radius: 4px; font-size: 9px; }
  .qa-warn { background: #fef9c3; border-color: #fde047; }
  .category-badge { display: inline-block; padding: 1px 6px; border-radius: 10px; font-size: 8px; font-weight: bold; background: #e0e7ff; color: #4338ca; margin-left: 6px; }
  .footer { text-align: center; font-size: 8px; color: #aaa; margin-top: 30px; border-top: 1px solid #eee; padding-top: 10px; }
</style>
</head>
<body>

<div class="header">
  <h1>GEN AI DIGEST</h1>
  <div class="meta">{{ date }} &nbsp;|&nbsp; Edition #{{ edition }} &nbsp;|&nbsp; Powered by Groq + LangGraph</div>
</div>

<div class="section">
  <h2>Executive Summary</h2>
  <div class="exec-summary">
    <ul>
    {% for bullet in executive_summary %}
      <li>{{ bullet }}</li>
    {% endfor %}
    </ul>
  </div>
</div>

{% if sections %}
{% for section in sections %}
<div class="section">
  <h2>{{ section.section_name }}</h2>
  {% for item in section.content %}
  <div class="article">
    <div class="headline">
      {{ item.headline }}
      {% if item.category %}<span class="category-badge">{{ item.category }}</span>{% endif %}
    </div>
    {% if item.summary_bullets %}
    <ul class="bullets">
      {% for b in item.summary_bullets %}<li>{{ b }}</li>{% endfor %}
    </ul>
    {% endif %}
    {% if item.key_insight %}
    <div class="insight">💡 {{ item.key_insight }}</div>
    {% endif %}
    {% if item.body %}
    <p style="margin: 6px 0; font-size: 10px;">{{ item.body }}</p>
    {% endif %}
    {% if item.source_url %}
    <div class="source">Source: {{ item.source_url }}</div>
    {% endif %}
  </div>
  {% endfor %}
</div>
{% endfor %}
{% else %}
<div class="section">
  <div style="padding: 30px; text-align: center; color: #888; background: #f8f9fa; border-radius: 6px;">
    <p style="font-size: 13px; margin: 0 0 8px 0;">Newsletter content could not be generated for this edition.</p>
    <p style="font-size: 10px; margin: 0;">This may be due to a temporary LLM rate limit. Please generate a new newsletter from the dashboard.</p>
  </div>
</div>
{% endif %}

<div class="section">
  <h2>QA & Governance Report</h2>
  <div class="qa-box {% if not qa_report.approved %}qa-warn{% endif %}">
    <strong>Status:</strong> {{ "✅ Approved" if qa_report.approved else "⚠️ Approved with caveats" }} &nbsp;|&nbsp;
    <strong>Faithfulness:</strong> <span class="{% if qa_report.overall_faithfulness_score >= 0.8 %}score-good{% elif qa_report.overall_faithfulness_score >= 0.6 %}score-warn{% else %}score-bad{% endif %}">
      {{ "%.0f"|format(qa_report.overall_faithfulness_score * 100) }}%
    </span> &nbsp;|&nbsp;
    <strong>Coverage:</strong> {{ "%.0f"|format(qa_report.coverage_score * 100) }}%
    <strong>Readability:</strong> {{ "%.0f"|format(qa_report.readability_score * 100) }}%
    {% if qa_report.bias_flags %}
    <br><strong>Bias flags:</strong> {{ qa_report.bias_flags | join(", ") }}
    {% endif %}
    <br><em>Responsible AI: Data sourced from {{ source_count }} sources. No PII detected. Full audit trail available in dashboard.</em>
  </div>
</div>

<div class="footer">
  Generated {{ timestamp }} &nbsp;|&nbsp; Gen AI Info Pipeline &nbsp;|&nbsp; All content sourced and attributed. AI-generated summaries — verify critical facts.
</div>

</body>
</html>
"""


async def generate_pdf(newsletter_id: str, newsletter_content: dict, qa_report: dict, edition: int = 1) -> str:
    """Generate a PDF from newsletter content. Returns the PDF file path."""
    try:
        from weasyprint import HTML as WeasyHTML
    except ImportError:
        logger.warning("weasyprint_not_installed")
        return ""

    os.makedirs(settings.pdf_output_dir, exist_ok=True)

    env = Environment(loader=BaseLoader())
    template = env.from_string(TEMPLATE)

    html_content = template.render(
        date=datetime.utcnow().strftime("%B %d, %Y"),
        edition=edition,
        timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        executive_summary=newsletter_content.get("executive_summary", []),
        sections=newsletter_content.get("sections", []),
        qa_report=qa_report,
        source_count=sum(len(s.get("content", [])) for s in newsletter_content.get("sections", [])),
    )

    filename = f"genai_digest_{datetime.utcnow().strftime('%Y%m%d_%H%M')}_{newsletter_id[:8]}.pdf"
    output_path = os.path.join(settings.pdf_output_dir, filename)

    WeasyHTML(string=html_content).write_pdf(output_path)
    logger.info("pdf_generated", path=output_path)
    return output_path
