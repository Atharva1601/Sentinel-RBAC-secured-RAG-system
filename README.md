# 🛡️ Sentinel — Secure RBAC-Secured RAG System

A **production-quality, document-only Retrieval-Augmented Generation (RAG) platform** built for enterprise use. Sentinel enforces **role-based access control (RBAC) at the vector database retrieval level**, ensuring users can only receive answers grounded in documents they are authorized to access.

> No model training. No hallucinations. No uncontrolled access.  
> Built for internal company documents, research papers, and knowledge bases.

---

## 🚀 Key Features

- **🔑 RBAC Enforced at Retrieval** — Department, role level, and clearance level filters are applied inside the Qdrant vector query. Unauthorized chunks never reach the LLM.
- **🧠 Production-Grade RAG Pipeline** — Multi-stage pipeline with HyDE, Hybrid Search (Dense + BM25), RRF fusion, Cross-Encoder reranking, and sliding-window context expansion.
- **💬 Streaming Chat Interface** — Token-by-token SSE streaming via `/query/stream`. Answers appear word-by-word.
- **🔄 Multi-Turn Conversations** — DB-backed session history with automatic query contextualization for follow-up questions.
- **⚡ Redis Query Cache** — RBAC-aware SHA-256 cache key. Cache auto-invalidates on model or permission changes.
- **📄 Async PDF Ingestion** — pdfplumber layout extraction with pytesseract OCR fallback. Non-blocking background ingest.
- **📊 Built-In Evaluation** — Custom LLM-as-a-Judge system scoring Faithfulness, Answer Relevance, Context Precision, and Context Recall.
- **🛡️ Zero-Hallucination Policy** — Decision gate blocks LLM calls when retrieval confidence is below calibrated thresholds.

---

## 🏗️ RAG Pipeline

```
User Query
  │
  ├─ Redis cache check  →  HIT: return cached SSE immediately
  │
  ├─ Query Contextualization  (multi-turn: rewrite follow-up as standalone question)
  │
  ├─ Query Decomposition  (len > 12 words + keyword gate → split into 2-3 sub-questions)
  │
  ├─ [Per sub-query, run in parallel]:
  │    ├─ HyDE: generate hypothetical answer (llama-3.1-8b-instant) → embed
  │    │    └─ Fallback: direct query embedding if Groq call fails
  │    └─ Qdrant vector search with RBAC filter → Top-K candidates
  │         (K=25 with HyDE / K=35 without)
  │
  ├─ BM25 sparse scoring on RBAC-filtered candidates
  ├─ Reciprocal Rank Fusion (RRF, k=60) — merges dense + sparse rankings
  │
  ├─ Cross-Encoder Reranker (ms-marco-MiniLM-L-6-v2) → Top-4
  │
  ├─ Sliding-Window Context Expansion (chunk ± 1 adjacent chunks)
  │
  ├─ Decision Gate → answer / soft_answer / no_info
  │    └─ no_info: refuse immediately, LLM never called
  │
  ├─ Groq LLM (llama-3.3-70b-versatile) → SSE streaming response
  │
  ├─ Persist conversation turn to DB
  └─ Cache response in Redis (1hr TTL)
```

---

## 🛡️ Authorization Model

Every document chunk stored in Qdrant carries three RBAC metadata fields:

| Field | Description |
|---|---|
| `owner_department` | Which department owns this document |
| `min_role_level` | Minimum role required (1=User, 2=Manager, 3=Admin) |
| `min_clearance_level` | Minimum clearance required |

RBAC is enforced **inside the Qdrant query** using a `Filter` with `must` conditions — unauthorized vectors are never retrieved, never scored, never sent to the LLM.

---

## ⚙️ Tech Stack

**Backend**
- **FastAPI** — async API with SSE streaming
- **Qdrant** — vector database (local path / Docker / Qdrant Cloud)
- **BAAI/bge-small-en-v1.5** — local CPU embeddings via `sentence-transformers` (384-dim, no API cost)
- **cross-encoder/ms-marco-MiniLM-L-6-v2** — local CPU cross-encoder reranker
- **Groq** — LLM inference (`llama-3.3-70b-versatile` for answers, `llama-3.1-8b-instant` for HyDE + contextualization)
- **SQLite / PostgreSQL** — user auth + conversation history (SQLAlchemy)
- **Redis** — query-level response cache (optional, graceful no-op if not configured)
- **structlog** — structured JSON logging
- **pydantic-settings** — centralized config from env vars

**Frontend**
- **React + TypeScript** (Vite)
- Token-by-token SSE streaming chat with source citations
- Admin dashboards for users, departments, and document management

**Deployment**
- Backend: Render (or any WSGI/ASGI host)
- Frontend: Vercel
- Qdrant: Qdrant Cloud free tier (1GB)

---

## 📂 Project Structure

```text
.
├── llm-se-backend/
│   ├── app/
│   │   ├── admin/          # PDF upload, ingestion, user & doc management
│   │   ├── api/            # /query, /query/stream, /eval/query endpoints
│   │   ├── audit/          # JSONL audit log per query
│   │   ├── auth/           # Bearer token auth + RBAC
│   │   ├── cache/          # Redis query cache
│   │   ├── config.py       # Centralized pydantic-settings config
│   │   ├── db/             # SQLAlchemy models + seed
│   │   ├── embeddings/     # BGE-small local embedding client
│   │   ├── errors/         # Global error handlers + structlog setup
│   │   ├── evaluation/     # LLM-as-a-Judge evaluation runner
│   │   ├── gates/          # Decision gate (answer / soft_answer / no_info)
│   │   ├── llm/            # Groq invocation, prompts, SSE streaming
│   │   ├── models/         # Pydantic request/response schemas
│   │   └── retrieval/      # HyDE, decompose, reranker, contextualize, retrieve
│   ├── data/               # Qdrant DB, SQLite DB, audit logs, eval results
│   └── requirements.txt
│
└── llm-se-frontend/
    └── frontend/
        └── src/
            ├── api/        # Typed API client
            ├── components/ # ChatBox with SSE streaming
            ├── context/    # AuthContext
            └── pages/      # Login, Chat, Admin (Users + Documents)
```

---

## 🔒 Security & Safety Guarantees

- RBAC enforced **inside the vector database query** — not post-retrieval filtering
- Redis cache keys include RBAC context — different roles always get different cached results
- `RBAC_VERSION` config field — bump it to instantly invalidate all cached responses when permissions change
- Decision gate prevents any LLM call when retrieval confidence is below threshold
- Explicit refusal message returned when no relevant context is found
- No training on user data; no external knowledge; no internet access

---

## 📈 Performance

| Metric | Value |
|---|---|
| Avg response latency | ~2–4s (first token via SSE) |
| Embedding model | BAAI/bge-small-en-v1.5 (local CPU, ~1–2s per 100 chunks) |
| Reranker | ms-marco-MiniLM-L-6-v2 (local CPU, ~80ms per 25 candidates) |
| Chunk size | 256 tokens / 64 overlap (token-based, recursive) |
| Top-K retrieval | 25 (HyDE active) / 35 (HyDE fallback) → reranked to Top-4 |
| Evaluation (LLM-as-Judge) | Faithfulness, Answer Relevance, Context Precision, Context Recall |

---

## 🚀 Running Locally

**Backend**
```bash
cd llm-se-backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend**
```bash
cd llm-se-frontend/frontend
npm install
npm run dev
```

**Environment variables** (`.env` in `llm-se-backend/`):
```
GROQ_API_KEY=...
QDRANT_LOCAL_URL=data/qdrant_db       # local path or http://localhost:6333
QDRANT_USE_CLOUD=false
REDIS_URL=                            # optional — leave empty to disable caching
ENVIRONMENT=development
```

---

## 📊 Evaluation

Run the built-in LLM-as-a-Judge evaluation against the 13-question golden dataset:

```bash
cd llm-se-backend
python -m app.evaluation.eval
```

Results are saved to `data/eval_<timestamp>.json`. Metrics are scored 1–5 (normalized to 100%):
- **Faithfulness** — are all claims strictly supported by retrieved context?
- **Answer Relevance** — does the answer directly address the question?
- **Context Precision** — how much of the retrieved context was actually useful?
- **Context Recall** — does retrieved context cover all ground truth facts?

### 📈 Latest Evaluation Benchmarks
Run against the 13-question golden dataset:

| Metric | Baseline Score | Target Score |
| :--- | :---: | :---: |
| **Decision Gate Success** | 100% | 100% |
| **Answer Relevance** | 93.8% | >95% |
| **Faithfulness** | 87.7% | >90% |
| **Context Precision** | 83.1% | >90% |
| **Context Recall** | **69.2%** | >85% |

---

## 🔮 Future Roadmap (Improving Recall)

The baseline evaluation highlights **Context Recall (69.2%)** as the primary area for optimization. The following improvements are planned:

1. **📷 OCR Integration for Scanned Documents**
   * Integrate an OCR pipeline (e.g., using `EasyOCR` or `PyMuPDF` with Tesseract) to parse text from scanned PDFs, images, and embedded diagrams which are currently missed by raw text parsers.

2. **📂 Hierarchical / Parent-Child Chunking**
   * Index smaller chunks (100 tokens) for high-precision vector matches, but retrieve and feed the wider parent chunk (500 tokens) to the LLM to provide richer context and raise recall.

3. **📊 Layout-Aware PDF Parsing**
   * Move from simple character/token splitting to layout-aware parsing (using `Unstructured` or `Marker`) to preserve tables, headers, and bullet points.

4. **🧠 Dense + Sparse Weights Tuning**
   * Fine-tune the Reciprocal Rank Fusion (RRF) weights between dense embeddings (`BAAI/bge-small-en-v1.5`) and sparse lexical search (`BM25`) based on evaluation feedback.

