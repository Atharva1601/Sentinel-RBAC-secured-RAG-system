from typing import Dict, List
from app.embeddings.hf_client import embed_text
from .chroma_client import get_chroma_collection

TOP_K = 7


def retrieve_authorized_documents(
    query: str,
    user: Dict,
) -> List[Dict]:
    """
    Retrieve top-K relevant documents with:
    - Query embeddings
    - RBAC enforced
    - Similarity scores returned

    RBAC rules:
    - shared users → can see ALL documents
    - dept users → can see their dept + shared docs
    """

    collection = get_chroma_collection()

    if user["department"] == "shared":
        where_filter = {
            "$and": [
                {"min_role_level": {"$lte": user["role_level"]}},
                {"min_clearance_level": {"$lte": user["clearance_level"]}},
            ]
        }
    else:
        where_filter = {
            "$and": [
                {
                    "$or": [
                        {"owner_department": {"$eq": user["department"]}},
                        {"owner_department": {"$eq": "shared"}},
                    ]
                },
                {"min_role_level": {"$lte": user["role_level"]}},
                {"min_clearance_level": {"$lte": user["clearance_level"]}},
            ]
        }

    query_embedding = embed_text(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=TOP_K,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    retrieved: List[Dict] = []

    for doc, meta, dist in zip(documents, metadatas, distances):
        similarity = 1.0 - (float(dist) / 2.0)

        retrieved.append(
            {
                "content": doc,
                "metadata": meta,
                "similarity": round(similarity, 4),
            }
        )

    return retrieved
