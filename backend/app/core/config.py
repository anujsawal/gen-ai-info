from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path

_ENV_FILES = [
    Path(__file__).resolve().parents[3] / ".env",  # project root (gen-ai-info/.env)
    Path(".env"),  # cwd fallback
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=[str(p) for p in _ENV_FILES], extra="ignore")

    # App
    app_env: str = "development"
    secret_key: str = "change_me_to_random_32_char_string"
    log_level: str = "INFO"
    pdf_output_dir: str = "./pdfs"

    # Database
    database_url: str = "postgresql+asyncpg://genai:genai_pass@localhost:5432/genai_info"

    # Groq LLM
    groq_api_key: str = ""
    llm_large: str = "llama-3.3-70b-versatile"
    llm_fast: str = "llama-3.1-8b-instant"

    # Embeddings (local sentence-transformers)
    embedding_model: str = "nomic-ai/nomic-embed-text-v1"
    embedding_dimension: int = 768

    # LangSmith
    langchain_api_key: str = ""
    langchain_project: str = "genai-info-pipeline"
    langchain_tracing_v2: str = "true"

    # Twilio WhatsApp
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14155238886"
    whatsapp_to: str = ""

    # Scheduling
    newsletter_cron_schedule: str = "0 8 * * 1"

    # Clustering
    cluster_min_size: int = 2
    cluster_max_articles_per_run: int = 100

    # Hallucination gate
    faithfulness_threshold: float = 0.7
    max_qa_retries: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()
