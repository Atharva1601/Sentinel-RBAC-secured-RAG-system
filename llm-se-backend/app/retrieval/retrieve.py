from typing import Dict, List, Any
import asyncio
import anyio
from rank_bm25 import BM25Okapi

from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    Range,
)

from app.config import settings
from app.embeddings.client import embed_text
from app.retrieval.qdrant_client import get_async_qdrant_client, get_collection_name
from app.retrieval.hyde import generate_hypothetical_answer
from app.retrieval.reranker import rerank
from app.retrieval.decompose import should_decompose, decompose_query

import structlog

log = structlog.get_logger()


def _build_rbac_filter(user: Dict) -> Filter:
    """
    Build a Qdrant Filter for RBAC enforcement.

    Rules:
    - "shared" department users see ALL docs where role_level and
      clearance_level are sufficient
    - Non-shared users see their own department + "shared" docs
      where role_level and clearance_level are sufficient
    """
    role_condition = FieldCondition(
        key="min_role_level",
        range=Range(lte=user["role_level"]),
    )
    clearance_condition = FieldCondition(
        key="min_clearance_level",
        range=Range(lte=user["clearance_level"]),
    )

    if user["department"] == "shared":
        return Filter(must=[role_condition, clearance_condition])

    # Non-shared: must match own department OR "shared" department
    dept_filter = Filter(
        should=[
            FieldCondition(
                key="owner_department",
                match=MatchValue(value=user["department"]),
            ),
            FieldCondition(
                key="owner_department",
                match=MatchValue(value="shared"),
            ),
        ]
    )

    return Filter(must=[dept_filter, role_condition, clearance_condition])


async def _search_qdrant(
    query_embedding: List[float],
    rbac_filter: Filter,
    top_k: int,
) -> List[Dict]:
    """
    Execute a single Qdrant vector search with RBAC filtering (async).

    Returns list of dicts with 'content', 'metadata', 'similarity' keys.
    """
    client = await get_async_qdrant_client()
    collection_name = get_collection_name()

    results = await client.query_points(
        collection_name=collection_name,
        query=query_embedding,
        query_filter=rbac_filter,
        limit=top_k,
        with_payload=True,
    )

    documents = []
    for point in results.points:
        payload = point.payload or {}
        content = payload.pop("content", "")

        documents.append({
            "content": content,
            "metadata": payload,
            "similarity": round(float(point.score), 4),
        })

    return documents


async def _expand_to_window(doc: Dict, window_size: int = 1) -> str:
    """
    Replace a chunk's content with a sliding window of adjacent chunks (async).

    Fetches chunks with indices in [chunk_index - window_size, chunk_index + window_size]
    from the same document source to keep context focused and avoid rate limits.
    """
    source = doc["metadata"].get("source")
    chunk_idx = doc["metadata"].get("chunk_index")

    if not source or chunk_idx is None:
        return doc["content"]

    try:
        client = await get_async_qdrant_client()
        collection_name = get_collection_name()

        target_indices = list(range(max(0, chunk_idx - window_size), chunk_idx + window_size + 1))

        results, _ = await client.scroll(
            collection_name=collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="source", match=MatchValue(value=source)),
                    FieldCondition(key="chunk_index", match=MatchAny(any=target_indices)),
                ]
            ),
            limit=2 * window_size + 3,
            with_payload=True,
        )

        if not results:
            return doc["content"]

        sorted_chunks = sorted(
            results,
            key=lambda p: p.payload.get("chunk_index", 0) if p.payload else 0,
        )

        window_text = "\n".join(
            p.payload.get("content", "") for p in sorted_chunks if p.payload
        )

        log.info(
            "window_expansion_done",
            source=source,
            center_chunk=chunk_idx,
            chunks_fused=len(sorted_chunks),
        )
        return window_text

    except Exception as e:
        log.warning("window_expansion_failed", source=source, chunk_idx=chunk_idx, error=str(e))
        return doc["content"]


def _reciprocal_rank_fusion(
    candidates: List[Dict],
    bm25_scores: List[float],
    k: int = 60,
) -> List[Dict]:
    """
    Merge Dense Vector search ranking and Sparse BM25 ranking using
    Reciprocal Rank Fusion (RRF).

    Formula: score = 1/(k + rank_vector) + 1/(k + rank_bm25)
    """
    if not candidates:
        return []

    # Get BM25 ranks
    # Sort candidate indices by their BM25 score in descending order
    bm25_ranked = sorted(
        enumerate(bm25_scores),
        key=lambda x: x[1],
        reverse=True,
    )

    # Map index in original candidate list -> rank position (1-based)
    bm25_ranks = {index: rank for rank, (index, _) in enumerate(bm25_ranked, start=1)}

    # Calculate RRF score for each candidate
    for index, doc in enumerate(candidates):
        vector_rank = index + 1  # Candidates is already pre-sorted by vector similarity
        bm25_rank = bm25_ranks[index]

        rrf_score = (1.0 / (k + vector_rank)) + (1.0 / (k + bm25_rank))
        doc["rrf_score"] = round(rrf_score, 6)

    # Sort candidates by their fused RRF score descending
    fused_candidates = sorted(candidates, key=lambda d: d["rrf_score"], reverse=True)
    return fused_candidates


async def retrieve_authorized_documents(
    query: str,
    user: Dict,
) -> List[Dict]:
    """
    Retrieve top-K relevant documents with the full RAG pipeline (async).

    Pipeline:
    1. Check if query should be decomposed -> get sub-queries
    2. For each sub-query: HyDE -> embed -> Qdrant search (RBAC filtered) in parallel
    3. Deduplicate results across sub-queries
    4. Rerank with cross-encoder -> Top-3
    5. Sliding-window context expansion in parallel

    Args:
        query: The user's question.
        user: User dict with username, department, role_level, clearance_level.

    Returns:
        List of top documents (usually 3), each with content, metadata,
        similarity, and rerank_score.
    """
    log.info("retrieval_start", query=query[:80], user=user.get("username"))

    # Query decomposition (run synchronously as it has its own logic)
    if should_decompose(query):
        sub_queries = decompose_query(query)
    else:
        sub_queries = [query]

    # RBAC filter is identical for all sub-queries
    rbac_filter = _build_rbac_filter(user)

    # Helper function to process one sub-query asynchronously
    async def process_sub_query(sq: str) -> List[Dict]:
        hypothetical = await generate_hypothetical_answer(sq)
        hyde_used = hypothetical is not None

        # Offload local CPU model embedding call to thread pool to prevent blocking the event loop
        if hyde_used:
            search_embedding = await anyio.to_thread.run_sync(embed_text, hypothetical)
            top_k = settings.TOP_K_WITH_HYDE
        else:
            search_embedding = await anyio.to_thread.run_sync(embed_text, sq)
            top_k = settings.TOP_K_WITHOUT_HYDE

        log.info(
            "hyde_result",
            sub_query=sq[:80],
            hyde_used=hyde_used,
            top_k=top_k,
        )

        # Qdrant vector search
        candidates = await _search_qdrant(search_embedding, rbac_filter, top_k)

        log.info(
            "vector_search_done",
            sub_query=sq[:80],
            num_candidates=len(candidates),
        )
        return candidates

    # Run HyDE + Vector search in parallel for all sub-queries
    tasks = [process_sub_query(sq) for sq in sub_queries]
    results = await asyncio.gather(*tasks)

    all_candidates: List[Dict] = []
    seen_contents: set = set()

    for candidates in results:
        # Deduplicate across sub-queries by content prefix hash
        for doc in candidates:
            content_key = doc["content"][:200]
            if content_key not in seen_contents:
                seen_contents.add(content_key)
                all_candidates.append(doc)

    if not all_candidates:
        log.warning("retrieval_empty", query=query[:80])
        return []

    # BM25 Scoring & Reciprocal Rank Fusion (RRF)
    try:
        tokenized_corpus = [doc["content"].lower().split() for doc in all_candidates]
        tokenized_query = query.lower().split()

        bm25 = BM25Okapi(tokenized_corpus)
        bm25_scores = bm25.get_scores(tokenized_query)

        hybrid_candidates = _reciprocal_rank_fusion(all_candidates, bm25_scores)
        log.info(
            "rrf_merge_complete",
            candidates=len(all_candidates),
            top_rrf_scores=[d.get("rrf_score") for d in hybrid_candidates[:3]],
        )
        all_candidates = hybrid_candidates
    except Exception as e:
        log.warning("bm25_rrf_failed", error=str(e), fallback="vector_only")

    # Cross-encoder reranking
    top_docs = await anyio.to_thread.run_sync(
        rerank,
        query,
        all_candidates,
        settings.TOP_K_RERANK,
    )

    # Context window expansion (matching chunk + preceding + succeeding) in parallel
    expansion_tasks = [_expand_to_window(doc) for doc in top_docs]
    expanded_contents = await asyncio.gather(*expansion_tasks)
    
    for doc, content in zip(top_docs, expanded_contents):
        # Sanitize text by removing null bytes to prevent API truncation
        doc["content"] = content.replace("\x00", "")

    log.info(
        "retrieval_complete",
        query=query[:80],
        total_candidates=len(all_candidates),
        final_docs=len(top_docs),
    )

    return top_docs
