from dotenv import load_dotenv

load_dotenv()

# Configure structured logging before any other imports
from app.errors.handlers import configure_logging, register_error_handlers

configure_logging()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.query import router as query_router
from app.api.query_stream import router as query_stream_router
from app.auth.me import router as auth_me_router
from app.admin.ingest import router as admin_ingest_router
from app.admin.documents import router as admin_documents_router
from app.admin.upload import router as admin_upload_router
from app.admin.users import router as admin_users_router
from app.admin.departments import router as admin_departments_router
from app.api.eval_query import router as eval_query_router
from app.db.database import engine, Base
from app.db.seed import seed_users_if_empty

import structlog

log = structlog.get_logger()


app = FastAPI(title="Secure Enterprise LLM Platform")

# Register error handlers
register_error_handlers(app)

# Hardened CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://senitel-rbac-secured-rag-system.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include API and administration routes
app.include_router(query_router)
app.include_router(query_stream_router)
app.include_router(auth_me_router)
app.include_router(admin_upload_router)
app.include_router(admin_ingest_router)
app.include_router(admin_documents_router)
app.include_router(admin_users_router)
app.include_router(admin_departments_router)
app.include_router(eval_query_router)


# Health check endpoint
@app.get("/health")
def health():
    return {"status": "ok"}


# Application startup lifecycle event
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    seed_users_if_empty()
    
    # Pre-warm local CPU models to eliminate cold starts
    from app.embeddings.client import pre_warm_embeddings
    from app.retrieval.reranker import pre_warm_reranker
    pre_warm_embeddings()
    pre_warm_reranker()
    
    log.info("app_started", title="Secure Enterprise LLM Platform")
