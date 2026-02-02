import os
from typing import List, Dict

from groq import Groq


MODEL_NAME = "llama-3.1-8b-instant"
MAX_TOKENS = 512
TEMPERATURE = 0.0


SYSTEM_PROMPT = """
You are an enterprise knowledge assistant.

You must answer using ONLY the provided context.
Do NOT use external knowledge, assumptions, or prior training data.

Rules:
- If the answer is fully supported by the context, answer clearly and concisely.
- If the context only partially answers the question, provide the partial answer
  and explicitly state what information is missing.
- If the context is irrelevant or does not contain the answer, respond with:
  "No relevant information found in the provided documents."

Formatting:
- Use bullet points for procedures or lists.
- Use short, clear paragraphs for explanations.
- Do not mention embeddings, retrieval, chunking, or system internals.

Tone:
- Professional
- Clear
- Practical
- Suitable for enterprise documentation and manuals.
"""

SOFT_MODE_NOTE = """
You are an enterprise knowledge assistant working with internal documents
such as manuals, policies, guides, and technical documentation.

Guidelines:
- Use ONLY the provided context.
- You MAY rephrase, summarize, and connect related statements found
  across the retrieved content.
- If the answer is partially supported, provide the best possible answer
  based on available information.
- Clearly state limitations ONLY if a critical detail is missing.
- Avoid saying "No relevant information found" unless the context is truly unrelated.

Summarization behavior:
- If asked to summarize a topic, produce a coherent summary using all
  relevant fragments found in the context.
- If asked to summarize a document, give a high-level overview even if
  only parts of the document are retrieved.
- If the summary is incomplete, add a short note such as:
  "This summary is based on the available sections of the document."

Restrictions:
- Do NOT introduce external facts, definitions, or assumptions.
- Do NOT speculate beyond what is implied in the documents.

Tone:
- Professional
- Helpful
- Explanatory
- Optimized for enterprise users reading internal documentation.
"""


PROMPT_SIMILARITY_THRESHOLD = 0.55


def select_documents_for_prompt(documents, max_docs=3):
    """
    Select top-N most relevant documents for LLM grounding.
    Do NOT over-filter — allow enough context for explanation.
    """

    if not documents:
        return []

    sorted_docs = sorted(
        documents,
        key=lambda d: d["similarity"],
        reverse=True,
    )

    return sorted_docs[:max_docs]


def build_user_prompt(query: str, documents: List[Dict]) -> str:
    """
    Build a grounded user prompt using retrieved documents.
    """

    context_blocks = []

    for i, doc in enumerate(documents, start=1):
        context_blocks.append(f"[Evidence {i}]\n{doc['content']}")

    context_text = "\n\n".join(context_blocks)

    return f"""Answer the question strictly using the information below.

{context_text}

Question:
{query}
"""


def generate_answer(
    query: str,
    documents: List[Dict],
    soft: bool = False,
) -> str:
    """
    Generate a grounded answer using Groq LLM.
    """

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    system_prompt = SYSTEM_PROMPT
    if soft:
        system_prompt = SYSTEM_PROMPT + "\n" + SOFT_MODE_NOTE

    messages = [
        {
            "role": "system",
            "content": system_prompt.strip(),
        },
        {
            "role": "user",
            "content": build_user_prompt(query, documents),
        },
    ]

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )

    return response.choices[0].message.content.strip()
