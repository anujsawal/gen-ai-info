import arxiv
from datetime import datetime, timezone
from app.core.logging import get_logger

logger = get_logger(__name__)


async def scrape_arxiv_source(source: dict) -> list[dict]:
    """Fetch recent ArXiv papers for given categories."""
    categories = source.get("categories", ["cs.AI"])
    max_papers = source.get("max_papers_per_run", 10)
    results = []

    try:
        query = " OR ".join(f"cat:{cat}" for cat in categories)
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_papers,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        for paper in client.results(search):
            abstract = paper.summary.replace("\n", " ").strip()
            full_text = f"Title: {paper.title}\n\nAuthors: {', '.join(str(a) for a in paper.authors)}\n\nAbstract: {abstract}"

            results.append({
                "url": paper.entry_id,
                "title": paper.title,
                "raw_text": full_text,
                "published_at": paper.published.replace(tzinfo=None) if paper.published else None,
                "source_name": source["name"],
                "metadata": {
                    "scraper": "arxiv",
                    "arxiv_id": paper.entry_id.split("/")[-1],
                    "authors": [str(a) for a in paper.authors],
                    "categories": paper.categories,
                    "pdf_url": paper.pdf_url,
                },
            })

    except Exception as e:
        logger.warning("arxiv_scrape_failed", source=source.get("name"), error=str(e))

    return results
