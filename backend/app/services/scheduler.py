"""
APScheduler for automated newsletter generation and delivery.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

scheduler = AsyncIOScheduler()


async def run_newsletter_job():
    """Scheduled job: generate and send newsletter."""
    from app.db.session import AsyncSessionLocal
    from app.graph.newsletter_graph import newsletter_graph
    from app.services.pdf_service import generate_pdf
    from app.services.whatsapp_service import send_pdf_to_whatsapp

    logger.info("scheduler_newsletter_job_started")
    try:
        async with AsyncSessionLocal() as db:
            result = await newsletter_graph.ainvoke({
                "db_session": db,
                "lookback_days": 7,
                "clusters": [],
                "cluster_articles": {},
                "pm_agenda": {},
                "designer_blueprint": {},
                "newsletter_content": {},
                "qa_report": {},
                "qa_retries": 0,
                "newsletter_id": "",
                "errors": [],
            })

        newsletter_id = result.get("newsletter_id", "")
        content = result.get("newsletter_content", {})
        qa = result.get("qa_report", {})

        if newsletter_id:
            pdf_path = await generate_pdf(newsletter_id, content, qa)
            if pdf_path:
                await send_pdf_to_whatsapp(pdf_path, "📰 Your weekly Gen AI Digest is ready!")
                logger.info("scheduled_newsletter_sent", newsletter_id=newsletter_id)

    except Exception as e:
        logger.error("scheduled_newsletter_failed", error=str(e))


async def run_ingestion_job():
    """Scheduled job: run ingestion pipeline."""
    from app.db.session import AsyncSessionLocal
    from app.graph.ingestion_graph import ingestion_graph

    logger.info("scheduler_ingestion_job_started")
    try:
        async with AsyncSessionLocal() as db:
            await ingestion_graph.ainvoke({
                "sources": [],
                "raw_items": [],
                "clean_items": [],
                "embedded_items": [],
                "cluster_map": {},
                "stored_article_ids": [],
                "errors": [],
                "db_session": db,
            })
        logger.info("scheduled_ingestion_done")
    except Exception as e:
        logger.error("scheduled_ingestion_failed", error=str(e))


def start_scheduler():
    """Start the APScheduler with configured cron jobs."""
    cron_parts = settings.newsletter_cron_schedule.split()
    if len(cron_parts) == 5:
        minute, hour, day, month, day_of_week = cron_parts
    else:
        minute, hour, day, month, day_of_week = "0", "8", "*", "*", "1"

    # Newsletter: weekly (configured schedule)
    scheduler.add_job(
        run_newsletter_job,
        CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week),
        id="weekly_newsletter",
        replace_existing=True,
    )

    # Ingestion: daily at 6am (2 hours before newsletter)
    scheduler.add_job(
        run_ingestion_job,
        CronTrigger(hour=6, minute=0),
        id="daily_ingestion",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("scheduler_started")
