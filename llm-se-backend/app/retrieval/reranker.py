from __future__ import annotations

import math
from typing import Dict, List

import structlog

log = structlog.get_logger()

# Lazy singleton model for cross-encoder reranking
_model = None
_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def _get_model():
    """Load the cross-encoder model once, reuse across all requests."""
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder

        log.info("reranker_loading", model=_MODEL_NAME)
        _model = CrossEncoder(_MODEL_NAME)
        log.info("reranker_loaded", model=_MODEL_NAME)
    return _model


def pre_warm_reranker() -> None:
    """Pre-load the CrossEncoder reranker model into memory."""
    _get_model()



def _sigmoid(x: float) -> float:
    """Safe sigmoid function to map raw logits to [0.0, 1.0]. Clamps to avoid overflow."""
    x = max(-20.0, min(20.0, x))
    return 1.0 / (1.0 + math.exp(-x))


def rerank(
    query: str,
    documents: List[Dict],
    top_k: int = 3,
) -> List[Dict]:
    """
    Rerank documents using a cross-encoder model.

    Scores each (query, document.content) pair jointly, then returns
    the top_k highest-scoring documents sorted by cross-encoder score.

    Args:
        query: The user's query text.
        documents: List of dicts with 'content', 'metadata', 'similarity' keys.
        top_k: Number of top documents to return.

    Returns:
        List of top_k documents sorted by rerank_score (descending).
        Each document dict has an added 'rerank_score' key.
    """
    if not documents:
        return []

    if len(documents) <= top_k:
        # Not enough candidates to rerank — return as-is
        for doc in documents:
            doc["rerank_score"] = doc.get("similarity", 0.0)
        return documents

    model = _get_model()

    # Build (query, document) pairs for the cross-encoder
    pairs = [[query, doc["content"]] for doc in documents]

    # Score all pairs at once (batched inference)
    scores = model.predict(pairs)

    # Attach scores (mapped with sigmoid to [0,1]) and sort
    for doc, score in zip(documents, scores):
        doc["rerank_score"] = _sigmoid(float(score))

    ranked = sorted(documents, key=lambda d: d["rerank_score"], reverse=True)

    log.info(
        "rerank_done",
        total_candidates=len(documents),
        top_k=top_k,
        top_scores=[round(d["rerank_score"], 4) for d in ranked[:top_k]],
    )

    return ranked[:top_k]
