# Gen AI Info Pipeline

A full-stack Gen AI information aggregation, clustering, and newsletter platform.

## Architecture

```
[Sources] → [Ingestion Graph] → [PostgreSQL + pgvector] → [Newsletter Graph] → [PDF] → [WhatsApp]
                                                                ↕
                                                        [LangSmith Evals]
```

## Stack
- **LLM**: Groq (Llama 3.3 70B + Llama 3.1 8B) — free tier
- **Embeddings**: sentence-transformers `nomic-embed-text-v1` — local, free
- **Clustering**: HDBSCAN (scikit-learn)
- **Database**: PostgreSQL + pgvector (Supabase free tier)
- **AI Framework**: LangChain + LangGraph + LangSmith
- **Backend**: FastAPI + Uvicorn
- **Frontend**: Next.js 15 + Tailwind + shadcn/ui
- **WhatsApp**: Twilio Sandbox

## Quick Start

### 1. Copy and fill in environment variables
```bash
cp .env.example .env
# Fill in: GROQ_API_KEY, DATABASE_URL (Supabase), LANGCHAIN_API_KEY, Twilio creds
```

### 2. Start with Docker (recommended)
```bash
docker-compose up --build
```

### 3. Run database migrations
```bash
cd backend
pip install alembic
alembic upgrade head
```

### 4. Open the dashboard
Navigate to http://localhost:3000

### 5. Run the ingestion pipeline
- Click "Pipeline" in the sidebar
- Click "Run Ingestion" to scrape all sources
- Click "Generate & Send" to produce a newsletter

## Key Files
- `backend/app/graph/ingestion_graph.py` — LangGraph ingestion pipeline
- `backend/app/graph/newsletter_graph.py` — LangGraph newsletter pipeline (4-agent loop)
- `backend/app/agents/team/` — PM, Designer, Developer, QA agents
- `backend/app/db/models.py` — Database schema
- `config/sources.yaml` — Configurable AI news sources
- `frontend/app/` — Next.js pages

## Environment Variables
See `.env.example` for all required variables.

Required:
- `GROQ_API_KEY` — from console.groq.com (free)
- `DATABASE_URL` — Supabase PostgreSQL connection string
- `LANGCHAIN_API_KEY` — from smith.langchain.com
- `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` + `WHATSAPP_TO` — Twilio sandbox

## Newsletter Schedule
Default: Every Monday at 8am (`NEWSLETTER_CRON_SCHEDULE=0 8 * * 1`)
Daily ingestion runs at 6am to populate content before newsletter generation.
