from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Env file (.env) is loaded automatically if present.
    Every field can be overridden by setting the corresponding
    environment variable (case-insensitive).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    ENVIRONMENT: Literal["development", "production"] = "development"

    # API Keys
    GROQ_API_KEY: str = ""
    HF_API_TOKEN: str = ""  # legacy — kept for backward compat
    VOYAGE_API_KEY: str = ""  # legacy — no longer used for embeddings

    # Embedding
    # Local sentence-transformers model — no API key, no rate limits.
    # bge-small-en-v1.5: 33M params, 384-dim, MTEB 62.17, ~300MB RAM
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSION: int = 384  # bge-small outputs 384-dim vectors

    # Chunking
    CHUNK_SIZE: int = 256       # tokens (not characters)
    CHUNK_OVERLAP: int = 64     # token overlap between chunks

    # Qdrant configuration
    QDRANT_USE_CLOUD: bool = False
    QDRANT_LOCAL_URL: str = ":memory:"
    QDRANT_CLOUD_URL: str = ""
    QDRANT_CLOUD_API_KEY: str = ""

    QDRANT_URL: str = "http://localhost:6333"  # fallback
    QDRANT_API_KEY: str = ""                   # fallback
    QDRANT_COLLECTION_NAME: str = "enterprise_docs"

    # Retrieval settings
    TOP_K_WITH_HYDE: int = 25       # candidates when HyDE is active
    TOP_K_WITHOUT_HYDE: int = 35    # candidates when HyDE falls back
    TOP_K_RERANK: int = 4           # final docs sent to LLM

    # Decision Gate Thresholds
    HARD_THRESHOLD: float = 0.08
    SOFT_THRESHOLD: float = 0.04

    # LLM configuration
    LLM_MODEL_NAME: str = "llama-3.3-70b-versatile"
    HYDE_MODEL_NAME: str = "llama-3.1-8b-instant"
    LLM_MAX_TOKENS: int = 1500   # 512 was too low — responses were getting cut off
    LLM_TEMPERATURE: float = 0.0

    # Redis (Phase 5 — pre-configured here)
    REDIS_URL: str = ""

    # RBAC Cache Settings
    RBAC_VERSION: str = "v1"  # bump when RBAC rules change to invalidate cache


@lru_cache()
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    s = Settings()
    # Strip any leading/trailing whitespace or newlines from string fields
    for field_name in Settings.model_fields:
        val = getattr(s, field_name)
        if isinstance(val, str):
            setattr(s, field_name, val.strip())
    return s


# Convenience alias — import as `from app.config import settings`
settings = get_settings()
