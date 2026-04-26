import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.services.scheduler import start_scheduler, scheduler

settings = get_settings()
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", env=settings.app_env)
    os.makedirs(settings.pdf_output_dir, exist_ok=True)

    # Set LangSmith env vars
    if settings.langchain_api_key:
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
        os.environ["LANGCHAIN_TRACING_V2"] = settings.langchain_tracing_v2

    start_scheduler()
    yield

    scheduler.shutdown(wait=False)
    logger.info("shutdown")


app = FastAPI(
    title="Gen AI Info Pipeline",
    description="AI-powered Gen AI news aggregation, clustering, and newsletter generation",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:3000", "http://localhost:80"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
from app.api.routes import ingest, newsletter, search, sources, governance, webhook

app.include_router(ingest.router, prefix="/api")
app.include_router(newsletter.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(governance.router, prefix="/api")
app.include_router(webhook.router, prefix="/api")


@app.get("/health")
async def health():
    s = get_settings()
    gemini_status = "not_configured"
    if s.gemini_api_key:
        try:
            import httpx
            r = httpx.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={s.gemini_api_key}",
                timeout=5,
            )
            gemini_status = "ok" if r.status_code == 200 else f"error_{r.status_code}"
        except Exception as e:
            gemini_status = f"error: {str(e)[:60]}"
    return {
        "status": "ok",
        "version": "1.0.0",
        "groq_configured": bool(s.groq_api_key),
        "gemini": gemini_status,
    }


@app.get("/api/pipeline/status")
async def pipeline_status():
    """Returns current scheduler job status."""
    jobs = [
        {"id": job.id, "next_run": job.next_run_time.isoformat() if job.next_run_time else None}
        for job in scheduler.get_jobs()
    ]
    return {"status": "running", "scheduled_jobs": jobs}
