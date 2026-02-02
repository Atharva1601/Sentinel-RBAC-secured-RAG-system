from typing import List, Dict

HARD_THRESHOLD = 0.50
SOFT_THRESHOLD = 0.40

TOP_N = 4
MIN_STRONG = 3


def decision_mode(documents: List[Dict]) -> str:
    """
    Decide how the system should respond.

    Logic:
    - Use top-N similarities (not global average)
    - Strong evidence from multiple chunks beats math noise
    """

    if not documents:
        return "no_info"

    similarities = []

    for doc in documents:
        try:
            similarities.append(float(doc.get("similarity", 0)))
        except (TypeError, ValueError):
            continue

    if not similarities:
        return "no_info"

    # Sort descending
    similarities.sort(reverse=True)

    top_similarities = similarities[:TOP_N]

    max_similarity = top_similarities[0]
    strong_count = sum(s >= SOFT_THRESHOLD for s in top_similarities)

    print(
        f"DECISION: top_similarities={top_similarities}, "
        f"strong_count={strong_count}, "
        f"HARD={HARD_THRESHOLD}, SOFT={SOFT_THRESHOLD}"
    )

    # Strong single signal
    if max_similarity >= HARD_THRESHOLD:
        return "answer"

    # Multiple moderate signals
    if strong_count >= MIN_STRONG:
        return "soft_answer"

    return "no_info"
