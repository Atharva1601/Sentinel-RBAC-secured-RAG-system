import os
from typing import List

from huggingface_hub import InferenceClient
import numpy as np

HF_EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"


def embed_text(text: str) -> List[float]:
    """
    Returns a flat embedding vector (length ~768).
    Handles HF responses:
      - List[float]
      - List[List[float]]
      - numpy.ndarray
    """

    hf_token = os.getenv("HF_API_TOKEN")
    if not hf_token:
        raise RuntimeError("HF_API_TOKEN not set")

    client = InferenceClient(
        model=HF_EMBEDDING_MODEL,
        token=hf_token,
    )

    response = client.feature_extraction(text)

    if isinstance(response, np.ndarray):
        if response.ndim == 2:
            embedding = response[0].tolist()
        elif response.ndim == 1:
            embedding = response.tolist()
        else:
            raise RuntimeError(f"Invalid numpy embedding shape: {response.shape}")

    elif isinstance(response, list):
        if len(response) == 0:
            raise RuntimeError("Empty embedding response")

        if isinstance(response[0], list):
            embedding = response[0]
        else:
            embedding = response

    else:
        raise RuntimeError(f"Unexpected HF embedding response type: {type(response)}")

    if not embedding or not isinstance(embedding[0], float):
        raise RuntimeError("Embedding vector is not List[float]")

    return embedding
