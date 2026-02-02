from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.query import router
from app.auth.me import router as auth_me_router
from app.admin.ingest import router as admin_ingest_router
from app.admin.documents import router as admin_documents_router
from app.admin.upload import router as admin_upload_router
from app.admin.ingest import router as admin_ingest_router
from app.admin.users import router as admin_users_router

app = FastAPI(title="Secure Enterprise LLM Platform")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(auth_me_router)
app.include_router(admin_upload_router)
app.include_router(admin_ingest_router)
app.include_router(admin_documents_router)
app.include_router(admin_ingest_router)
app.include_router(admin_users_router)


@app.get("/health")
def health():
    return {"status": "ok"}
