from app.retrieval.chroma_client import get_chroma_collection
import numpy as np

collection = get_chroma_collection()

result = collection.get(limit=1, include=["embeddings"])

embeddings = result.get("embeddings")

if embeddings is None:
    print("❌ No embeddings key returned")
elif len(embeddings) == 0:
    print("❌ Embeddings list is empty")
else:
    vec = embeddings[0]

    if isinstance(vec, np.ndarray):
        dim = vec.shape[0]
    else:
        dim = len(vec)

    print("✅ Embeddings exist")
    print("📐 Embedding dimension:", dim)
