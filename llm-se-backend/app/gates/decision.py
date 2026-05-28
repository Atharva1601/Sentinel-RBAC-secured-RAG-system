from typing import List, Dict

from app.config import settings

import structlog

log = structlog.get_logger()

TOP_N = 4
MIN_STRONG = 3


def decision_mode(documents: List[Dict]) -> str:
    """
    Decide how the system should respond.

    Logic:
    - Use top-N similarities (not global average)
    - Strong evidence from multiple chunks beats math noise

    Returns:
        "answer" — strong single signal above HARD_THRESHOLD
        "soft_answer" — multiple moderate signals above SOFT_THRESHOLD
        "no_info" — insufficient relevance
    """

    if not documents:
        return "no_info"

    similarities = []

    for doc in documents:
        try:
            # Prefer rerank_score if available, otherwise use similarity
            score = doc.get("rerank_score", doc.get("similarity", 0))
            similarities.append(float(score))
        except (TypeError, ValueError):
            continue

    if not similarities:
        return "no_info"

    # Sort descending
    similarities.sort(reverse=True)

    top_similarities = similarities[:TOP_N]

    max_similarity = top_similarities[0]
    strong_count = sum(s >= settings.SOFT_THRESHOLD for s in top_similarities)

    log.info(
        "decision_gate",
        top_similarities=top_similarities,
        strong_count=strong_count,
        hard_threshold=settings.HARD_THRESHOLD,
        soft_threshold=settings.SOFT_THRESHOLD,
    )

    # Strong single signal
    if max_similarity >= settings.HARD_THRESHOLD:
        return "answer"

    # Multiple moderate signals
    if strong_count >= MIN_STRONG:
        return "soft_answer"

    return "no_info"
