from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PayloadSchemaType

from app.config import settings

import structlog

log = structlog.get_logger()

# ── Module-level singleton ────────────────────────────────────
_client: QdrantClient | None = None
_async_client: AsyncQdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    """
    Return the singleton Qdrant client, initializing on first call.

    Connection modes:
    - settings.QDRANT_USE_CLOUD = False → local (in-memory or docker URL)
    - settings.QDRANT_USE_CLOUD = True → cloud URL + cloud API key
    """
    global _client
    if _client is not None:
        return _client

    if settings.QDRANT_USE_CLOUD:
        url = settings.QDRANT_CLOUD_URL
        api_key = settings.QDRANT_CLOUD_API_KEY
        mode = "cloud"
    else:
        url = settings.QDRANT_LOCAL_URL
        api_key = ""
        if url == ":memory:":
            mode = "in-memory"
        elif url.startswith("http://") or url.startswith("https://"):
            mode = "local-docker"
        else:
            mode = "path-persistence"

    if url == ":memory:":
        _client = QdrantClient(location=":memory:")
        log.info("qdrant_connected", mode=mode)
    elif url.startswith("http://") or url.startswith("https://"):
        kwargs = {"url": url}
        if api_key:
            kwargs["api_key"] = api_key
        _client = QdrantClient(**kwargs)
        log.info("qdrant_connected", mode=mode, url=url[:40] if url else "None")
    else:
        # Treat as local folder path, e.g. "data/qdrant_db"
        _client = QdrantClient(path=url)
        log.info("qdrant_connected", mode=mode, path=url)

    # Ensure collection exists with correct vector config
    _ensure_collection()

    return _client


def get_collection_name() -> str:
    """Return the configured collection name."""
    return settings.QDRANT_COLLECTION_NAME


def _ensure_collection() -> None:
    """
    Create the enterprise_docs collection if it doesn't already exist,
    and ensure all payload indexes required for RBAC filtering are present.

    Qdrant Cloud (unlike local mode) requires explicit payload indexes on
    any field used in a filter condition.
    """
    global _client
    assert _client is not None

    collection_name = settings.QDRANT_COLLECTION_NAME

    # Check if collection already exists
    collections = _client.get_collections().collections
    existing_names = [c.name for c in collections]

    if collection_name not in existing_names:
        _client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=settings.EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )
        log.info(
            "qdrant_collection_created",
            name=collection_name,
            dim=settings.EMBEDDING_DIMENSION,
        )
    else:
        log.info("qdrant_collection_exists", name=collection_name)

    # Create payload indexes required for RBAC filtering (safe to call even if they exist)
    _ensure_payload_indexes(_client, collection_name)


def _ensure_payload_indexes(client: QdrantClient, collection_name: str) -> None:
    """
    Create payload indexes for all fields used in RBAC and window-expansion filters.

    Qdrant Cloud enforces that numeric/keyword fields used in filters must be
    explicitly indexed. These calls are idempotent — safe to run on every startup.
    """
    integer_fields = ["min_role_level", "min_clearance_level", "chunk_index"]
    keyword_fields = ["owner_department", "source"]

    for field in integer_fields:
        client.create_payload_index(
            collection_name=collection_name,
            field_name=field,
            field_schema=PayloadSchemaType.INTEGER,
        )
    for field in keyword_fields:
        client.create_payload_index(
            collection_name=collection_name,
            field_name=field,
            field_schema=PayloadSchemaType.KEYWORD,
        )
    log.info("qdrant_payload_indexes_ensured", collection=collection_name)


async def _ensure_collection_async(client: AsyncQdrantClient) -> None:
    """
    Create the enterprise_docs collection asynchronously if it doesn't exist,
    and ensure all RBAC payload indexes are present.
    """
    collection_name = settings.QDRANT_COLLECTION_NAME
    collections = (await client.get_collections()).collections
    existing_names = [c.name for c in collections]

    if collection_name not in existing_names:
        await client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=settings.EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )
        log.info(
            "qdrant_async_collection_created",
            name=collection_name,
            dim=settings.EMBEDDING_DIMENSION,
        )
    else:
        log.info("qdrant_async_collection_exists", name=collection_name)

    # Use the sync singleton client to create indexes (idempotent, safe on every startup)
    import anyio
    await anyio.to_thread.run_sync(
        lambda: _ensure_payload_indexes(get_qdrant_client(), collection_name)
    )


async def get_async_qdrant_client() -> AsyncQdrantClient:
    """
    Return the singleton AsyncQdrantClient, initializing on first call.
    """
    global _async_client
    if _async_client is not None:
        return _async_client

    if settings.QDRANT_USE_CLOUD:
        url = settings.QDRANT_CLOUD_URL
        api_key = settings.QDRANT_CLOUD_API_KEY
        mode = "cloud"
    else:
        url = settings.QDRANT_LOCAL_URL
        api_key = ""
        if url == ":memory:":
            mode = "in-memory"
        elif url.startswith("http://") or url.startswith("https://"):
            mode = "local-docker"
        else:
            mode = "path-persistence"

    if url == ":memory:":
        _async_client = AsyncQdrantClient(location=":memory:")
        log.info("qdrant_async_connected", mode=mode)
    elif url.startswith("http://") or url.startswith("https://"):
        kwargs = {"url": url}
        if api_key:
            kwargs["api_key"] = api_key
        _async_client = AsyncQdrantClient(**kwargs)
        log.info("qdrant_async_connected", mode=mode, url=url[:40] if url else "None")
    else:
        # Treat as local folder path, e.g. "data/qdrant_db"
        _async_client = AsyncQdrantClient(path=url)
        log.info("qdrant_async_connected", mode=mode, path=url)

    # Ensure collection exists in the async client's database
    await _ensure_collection_async(_async_client)

    return _async_client

