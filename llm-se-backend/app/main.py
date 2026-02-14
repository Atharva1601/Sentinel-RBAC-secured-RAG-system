from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.api.query import router as query_router
from app.auth.me import router as auth_me_router
from app.admin.ingest import router as admin_ingest_router
from app.admin.documents import router as admin_documents_router
from app.admin.upload import router as admin_upload_router
from app.admin.users import router as admin_users_router

app = FastAPI(title="Secure Enterprise LLM Platform")

# =========================
# CORS (HARDENED)
# =========================
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


# =========================
# ROUTERS
# =========================
app.include_router(query_router)
app.include_router(auth_me_router)
app.include_router(admin_upload_router)
app.include_router(admin_ingest_router)
app.include_router(admin_documents_router)
app.include_router(admin_users_router)


# =========================
# HEALTH CHECK
# =========================
@app.get("/health")
def health():
    return {"status": "ok"}
