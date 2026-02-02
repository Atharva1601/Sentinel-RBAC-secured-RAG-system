import os
import chromadb


COLLECTION_NAME = "enterprise_docs"

_client = None
_collection = None


def get_chroma_collection():
    """
    Returns a singleton Chroma collection backed by persistent storage.

    IMPORTANT:
    - Uses PersistentClient (not Client + Settings)
    - Path is resolved from project root
    - Must match ingestion scripts EXACTLY
    """
    global _client, _collection

    if _collection is not None:
        return _collection

    BASE_DIR = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )

    CHROMA_PATH = os.path.join(BASE_DIR, "data", "chroma")
    os.makedirs(CHROMA_PATH, exist_ok=True)

    _client = chromadb.PersistentClient(path=CHROMA_PATH)

    _collection = _client.get_or_create_collection(name=COLLECTION_NAME)

    print("🔍 Chroma persist path:", CHROMA_PATH)
    print("🔍 Collection name:", COLLECTION_NAME)
    print("🔍 Collection count (on load):", _collection.count())

    return _collection
