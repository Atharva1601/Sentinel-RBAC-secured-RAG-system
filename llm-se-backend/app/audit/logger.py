import json
import os
from datetime import datetime
from typing import Dict, List


AUDIT_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..",
    "data",
    "audit_logs.jsonl",
)


def log_audit_event(
    *,
    request_id: str,
    user: Dict,
    query: str,
    decision_mode: str,
    max_similarity: float | None,
    llm_called: bool,
    sources: List[Dict] | None,
):
    """
    Append a single audit event as JSONL.
    """

    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "request_id": request_id,
        "user": {
            "username": user.get("username"),
            "department": user.get("department"),
            "role_level": user.get("role_level"),
            "clearance_level": user.get("clearance_level"),
        },
        "query": query,
        "decision_mode": decision_mode,
        "max_similarity": max_similarity,
        "llm_called": llm_called,
        "sources": sources or [],
    }

    os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)

    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
