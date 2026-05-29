from typing import List

import structlog

from app.config import settings

log = structlog.get_logger()

# Lazy singleton model
# Loaded once on first use, then reused across all requests.
# Load is ~1s (model is ~90MB on disk, ~300MB in RAM).
_model = None


def _get_model():
    """Return the singleton SentenceTransformer model, loading on first call."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        log.info("embedding_model_loading", model=settings.EMBEDDING_MODEL)
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
        log.info(
            "embedding_model_loaded",
            model=settings.EMBEDDING_MODEL,
            dim=_model.get_sentence_embedding_dimension(),
        )
    return _model


def pre_warm_embeddings() -> None:
    """Pre-load the SentenceTransformer embedding model into memory."""
    _get_model()



def embed_text(text: str) -> List[float]:
    """
    Embed a single text string into a vector (query mode).

    BGE models expect a query prefix for retrieval tasks:
    "Represent this sentence: {text}" — applied automatically by the model
    when encode_kwargs are passed.

    Used at query time for embedding user queries
    (or HyDE hypothetical answers).

    Args:
        text: The text to embed.

    Returns:
        A list of floats (384-dim for bge-small-en-v1.5).
    """
    model = _get_model()

    # BGE query prefix improves retrieval quality
    prefixed = f"Represent this sentence for searching relevant passages: {text}"
    embedding = model.encode(
        prefixed,
        normalize_embeddings=True,  # cosine similarity works correctly
        show_progress_bar=False,
    )
    return embedding.tolist()


def embed_batch(texts: List[str]) -> List[List[float]]:
    """
    Embed multiple texts in a single local inference call.

    No rate limits, no API delays — all inference runs locally.
    100 chunks typically complete in 1-3 seconds on CPU.

    Used at ingestion time for bulk embedding of PDF chunks.

    Args:
        texts: List of text strings to embed (document passages).

    Returns:
        List of embedding vectors, one per input text.
    """
    if not texts:
        return []

    model = _get_model()

    log.info("embed_batch_start", num_texts=len(texts), model=settings.EMBEDDING_MODEL)

    # BGE documents/passages do NOT get any prefix
    embeddings = model.encode(
        texts,
        batch_size=8,              # reduced from 64 to 8 to prevent RAM spikes (OOM) on Railway
        normalize_embeddings=True, # cosine similarity works correctly
        show_progress_bar=False,
        convert_to_numpy=True,
    )

    log.info("embed_batch_done", num_texts=len(texts))

    return [emb.tolist() for emb in embeddings]
