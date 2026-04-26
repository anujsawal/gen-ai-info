# Architecture

## System Overview

```
                    ┌─────────────────────────────────────────────┐
                    │              GitHub (master branch)          │
                    └──────────────┬──────────────────────────────┘
                                   │ git push triggers
                    ┌──────────────▼──────────┐  ┌───────────────┐
                    │   Railway (Backend)      │  │ Vercel (UI)   │
                    │   FastAPI + LangGraph    │  │ Next.js 15    │
                    │   Docker container       │  │ Edge network  │
                    └──────────────┬──────────┘  └───────┬───────┘
                                   │                     │
                    ┌──────────────▼─────────────────────▼───────┐
                    │              Supabase                        │
                    │   PostgreSQL + pgvector                      │
                    │   8 tables, HNSW indexes, 768-dim vectors    │
                    └─────────────────────────────────────────────┘
```

## Data Flow

### Ingestion Pipeline (daily at 6am)

```
config/sources.yaml ──┐
DB active sources ────┤
                      ▼
              ┌───────────────┐
              │  scraper_node │  Concurrent: web (httpx), YouTube (transcript API),
              │               │  RSS/newsletter (feedparser), ArXiv (arxiv library)
              └───────┬───────┘
                      │ raw_items: [{url, title, raw_text, published_at, source_name}]
                      ▼
              ┌───────────────┐
              │  cleaner_node │  Normalize whitespace, remove boilerplate,
              │               │  deduplicate by URL hash
              └───────┬───────┘
                      │ clean_items (subset of raw_items)
                      ▼
              ┌───────────────┐
              │ embedder_node │  fastembed (nomic-embed-text-v1, ONNX)
              │               │  768-dim vectors, batched, thread pool
              └───────┬───────┘
                      │ embedded_items (items + embedding vector)
                      ▼
              ┌───────────────┐
              │clusterer_node │  HDBSCAN, min_cluster_size=2
              │               │  Groups semantically similar articles
              └───────┬───────┘
                      │ cluster_map: {cluster_key → [item_indices]}
                      ▼
              ┌───────────────┐
              │ storage_node  │  Bulk inserts: Source → RawContent → Article →
              │               │  Chunk (with embeddings) → Cluster → AuditLog
              └───────────────┘
```

### Newsletter Pipeline (every Monday 8am, or on-demand)

```
              ┌───────────────┐
              │retrieval_node │  SELECT articles WHERE published_at >= now()-7d
              │               │  OR (published_at IS NULL AND created_at >= now()-7d)
              │               │  ORDER BY importance_score DESC, LIMIT 100
              └───────┬───────┘
                      │ clusters[], cluster_articles{}
                      ▼
              ┌───────────────┐
              │   pm_node     │  Llama 3.3 70B (temp=0.3)
              │  AI Curator   │  Enforces: vendor cap (≤2/company), source diversity
              │               │  (≥3 sources), no marketing pages, no duplicates
              └───────┬───────┘
                      │ pm_agenda: {top_stories, deep_dive, quick_bites, rejected}
                      ▼
              ┌───────────────┐
              │designer_node  │  Llama 3.1 8B (fast, temp=0.2)
              │               │  Maps stories to sections, assigns formats/tone
              └───────┬───────┘
                      │ designer_blueprint: {sections[], newsletter_title}
                      ▼
              ┌───────────────┐     ◄── qa feedback on retry
              │developer_node │  Llama 3.3 70B (temp=0.4)
              │               │  Writes headlines, bullets, deep-dives
              │               │  Grounds all claims in source text
              └───────┬───────┘
                      ▼
              ┌───────────────┐
              │   qa_node     │  Llama 3.3 70B (temp=0.1)
              │               │  Faithfulness check, vendor bias check (>40% = reject),
              │               │  ArXiv section integrity, duplicate detection
              └───────┬───────┘
                      │
              ┌───────▼───────┐
              │ approved?     │──── NO (retries < 2) ──► developer_node
              └───────┬───────┘
                   YES│
                      ▼
              ┌───────────────┐
              │   save_node   │  Newsletter → DB, generate PDF (WeasyPrint)
              │               │  Send WhatsApp message with PDF URL
              └───────────────┘
```

## Database Schema

```
sources          — configured scraping sources (name, url, type, fetch_config, active)
raw_content      — raw scraped text (url, title, raw_text, scraped_at, processed)
articles         — processed articles (title, summary, embedding[768], published_at,
                   importance_score, hallucination_score, cluster_id)
chunks           — text chunks with embeddings for RAG (content, embedding[768])
clusters         — HDBSCAN groups (label, centroid_embedding[768], article_count)
newsletters      — generated editions (content JSON, pdf_path, status, quality_metrics)
audit_log        — agent action trail (entity, action, actor, reasoning, in/out snapshots)
eval_metrics     — LangSmith run IDs + quality scores per article/newsletter
```

Vector indexes: HNSW on `articles.embedding` and `chunks.embedding` (ivfflat + hnsw, 768 dims, cosine distance).

## API Routes

```
POST /api/ingest/trigger              # Start ingestion pipeline (background)
POST /api/ingest/upload               # Upload PDF/TXT/MD for RAG

POST /api/newsletter/generate         # Generate newsletter from last N days
POST /api/newsletter/generate-and-send# Generate + send to WhatsApp
POST /api/newsletter/send/{id}        # Send existing newsletter to WhatsApp
GET  /api/newsletter/list             # List all newsletters
GET  /api/newsletter/{id}             # Get full newsletter content
GET  /api/newsletter/{id}/pdf         # Download PDF (regenerates if missing)

GET  /api/sources                     # List all sources
POST /api/sources                     # Add new source
POST /api/sources/detect              # Auto-detect source type from URL
PATCH /api/sources/{id}/toggle        # Enable/disable source
DELETE /api/sources/{id}              # Remove source

GET  /api/search?q=...                # Semantic search (pgvector cosine similarity)

GET  /api/governance/audit-log        # Full agent action trail
GET  /api/governance/metrics/summary  # Quality metrics across newsletters
GET  /api/governance/lineage/article/{id}   # Article provenance
GET  /api/governance/lineage/newsletter/{id} # Newsletter agent decisions

POST /api/webhook/whatsapp            # Twilio inbound webhook (on-demand requests)

GET  /health                          # Health check
GET  /api/pipeline/status             # Scheduler job status
```

## Deployment

### Production topology

```
GitHub master branch
       │
       ├──► Railway (auto-deploy on push)
       │    Docker build from /backend/Dockerfile
       │    Env vars: GROQ_API_KEY, DATABASE_URL, TWILIO_*, etc.
       │    URL: gen-ai-info-production.up.railway.app
       │
       └──► Vercel (auto-deploy on push)
            Root dir: /frontend, framework: Next.js
            Build env: NEXT_PUBLIC_API_URL=https://gen-ai-info-production.up.railway.app
            URL: frontend-amber-sigma-37.vercel.app
```

### Local topology

```
docker-compose up --build
       │
       ├── backend:8000   (FastAPI)  ─┐
       ├── frontend:3000  (Next.js)   ├──► nginx:80 (single entry point)
       └── nginx:80       (proxy)    ─┘
```

Nginx routes: `/api/*` → backend, `/health` → backend, `/*` → frontend.

## Agent Design Decisions

**Why LangGraph instead of a single prompt?**
Each agent has a distinct job with different temperature, model size, and failure modes. LangGraph makes the retry loop (QA → Developer) explicit and observable. LangSmith traces every node.

**Why Llama 3.1 8B for the Designer?**
Layout decisions are mechanical (map story → section type). The 8B model is fast and free. The 70B model is reserved for judgment tasks (PM curation, QA evaluation, content writing).

**Why HDBSCAN over K-means?**
ArXiv papers cluster tightly on subtopics; blog posts don't. HDBSCAN finds natural clusters without requiring a fixed K, and marks outliers as noise rather than forcing them into a cluster.

**Why fastembed over sentence-transformers?**
sentence-transformers requires PyTorch (CUDA packages = 3-4GB Docker image). fastembed uses ONNX Runtime — same model (nomic-embed-text-v1), same vectors, under 1GB image.

**Why not store PDFs in object storage?**
Railway has ephemeral storage — PDFs are regenerated on demand from the Newsletter DB record if the file is missing. The `/api/newsletter/{id}/pdf` endpoint handles this transparently.

## Governance & Observability

Every agent action is logged to `audit_log` with full input/output snapshots. LangSmith traces the newsletter graph end-to-end. The QA agent scores faithfulness, coverage, and readability on every run. Presidio runs PII detection on all ingested content before storage.
