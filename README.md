# Gen AI Info Pipeline

> A fully automated AI research digest — from raw sources to a curated newsletter delivered to your WhatsApp every week.

## The Problem We're Solving

The AI space moves fast. Between ArXiv papers, model releases, research blogs, YouTube talks, and newsletters, there's too much signal and not enough time. This system reads everything so you don't have to — and delivers a concise, curated digest every Monday morning.

## What It Does

Every day at 6am, the pipeline scrapes configured sources across the web. Every Monday at 8am, a team of four AI agents collaborates to turn that raw content into a structured newsletter — then sends it as a PDF link to your WhatsApp.

You can also trigger any part of the pipeline on-demand from the dashboard.

```
Sources → Ingest → Embed → Cluster → Newsletter Agents → PDF → WhatsApp
```

## The Agent Team

The newsletter isn't written by a single LLM prompt. Four agents work in sequence with a feedback loop:

| Agent | Role | What it actually does |
|---|---|---|
| **AI Curator (PM)** | Editor-in-Chief | Picks stories, enforces vendor diversity (max 2 per company), rejects marketing fluff |
| **Designer** | Layout architect | Assigns each story a section, format, and tone |
| **Developer** | Content writer | Writes headlines, bullets, and deep-dives grounded in source text |
| **QA** | Quality gate | Checks faithfulness, rejects biased or duplicate content, loops back if needed |

If QA rejects, the Developer rewrites based on specific feedback. Max 2 retry loops.

## Sources

Configured in `config/sources.yaml`. Currently active:

| Type | Sources |
|---|---|
| **Websites** | Anthropic Blog, OpenAI Blog, Hugging Face Blog, VentureBeat AI, DeepMind Blog |
| **YouTube** | Two Minute Papers, AI Explained |
| **Newsletters** | Ahead of AI, TLDR AI, Ben's Bites |
| **ArXiv** | cs.AI, cs.LG, cs.CL (3 papers each per run) |

Add new sources from the dashboard without touching code — paste a URL, auto-detect type, save.

## Stack

| Layer | Technology | Why |
|---|---|---|
| LLM | Groq (Llama 3.3 70B + 3.1 8B) | Free tier, fast inference |
| Embeddings | fastembed / nomic-embed-text-v1 | ONNX, no GPU, runs anywhere |
| Clustering | HDBSCAN | Density-based, no fixed cluster count needed |
| Database | PostgreSQL + pgvector (Supabase) | Vector similarity search, free tier |
| AI Framework | LangChain + LangGraph + LangSmith | Agent orchestration + tracing |
| Backend | FastAPI + Uvicorn | Async, typed, OpenAPI docs at `/api/docs` |
| Frontend | Next.js 15 + Tailwind + shadcn/ui | Dashboard, pipeline controls, newsletter viewer |
| Delivery | Twilio WhatsApp Sandbox | Free sandbox for personal use |
| Backend hosting | Railway | Docker-based, auto-deploys from GitHub |
| Frontend hosting | Vercel | Git-connected, preview URLs on every branch |

## Quick Start (Local)

```bash
# 1. Copy and fill env vars
cp .env.example .env

# 2. Start everything (backend + frontend + nginx on port 80)
docker-compose up --build

# 3. Run migrations (first time only)
cd backend && alembic upgrade head

# 4. Open dashboard
open http://localhost
```

## Quick Start (Production)

Backend is on Railway, frontend is on Vercel, database is on Supabase. See `ARCHITECTURE.md` for the full deployment topology.

## Key Files

```
backend/
  app/
    graph/
      ingestion_graph.py     # LangGraph ingestion pipeline (5 nodes)
      newsletter_graph.py    # LangGraph newsletter pipeline (6 nodes + QA loop)
    agents/
      team/                  # pm_agent, designer_agent, developer_agent, qa_agent
      scrapers/              # web_scraper, youtube_agent, newsletter_agent, arxiv_agent
      processing/            # embedder, cleaner, clusterer
    api/routes/              # FastAPI route handlers
    db/models.py             # SQLAlchemy schema
  config/sources.yaml        # Source configuration (edit to add/remove sources)
frontend/
  app/                       # Next.js pages (pipeline, sources, newsletters, search)
  lib/api.ts                 # All API calls in one place
```

## Environment Variables

See `.env.example` for the full list. Required:

```
GROQ_API_KEY          # groq.com — free
DATABASE_URL          # Supabase PostgreSQL connection string
LANGCHAIN_API_KEY     # smith.langchain.com — free
TWILIO_ACCOUNT_SID    # twilio.com
TWILIO_AUTH_TOKEN
TWILIO_WHATSAPP_FROM  # whatsapp:+14155238886 (sandbox)
WHATSAPP_TO           # your number e.g. whatsapp:+919899437726
```

## Newsletter Schedule

| Job | Schedule | What it does |
|---|---|---|
| Ingestion | Daily at 6am | Scrapes all active sources, embeds, clusters, stores |
| Newsletter | Every Monday at 8am | Generates digest from last 7 days, sends to WhatsApp |

Both can be triggered on-demand from the Pipeline page.
