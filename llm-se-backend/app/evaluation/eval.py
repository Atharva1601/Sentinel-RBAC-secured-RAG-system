import os
import sys
import json
import time
import re
import asyncio
import httpx
from datetime import datetime
from typing import Dict, List, Any, Optional

# Ensure correct encoding on Windows to prevent output errors
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Force backend root directory onto sys.path to access configurations
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from dotenv import load_dotenv

load_dotenv()

from app.config import settings
from groq import AsyncGroq

# Configuration Settings
API_BASE = os.getenv("EVAL_API_BASE", "http://127.0.0.1:8000")
EVAL_USER = "admin"  # Bearer token (seeded username)
DELAY_BETWEEN_QUERIES = 8.0  # seconds to respect Groq API RPM limits
JUDGE_MODEL_NAME = "llama-3.3-70b-versatile"


# Golden Dataset
TEST_DATASET = [
    # DL (Attention is all you need)
    {
        "question": "What is the attention mechanism in transformers?",
        "ground_truth": (
            "The attention mechanism allows the model to focus on different parts "
            "of the input sequence when producing output. It computes a weighted sum "
            "of values based on the compatibility of queries and keys."
        ),
    },
    {
        "question": "What is self-attention and how does it work?",
        "ground_truth": (
            "Self-attention, or intra-attention, relates different positions of a "
            "single sequence to compute a representation of the same sequence. "
            "It uses queries, keys, and values derived from the same input."
        ),
    },
    {
        "question": "What is multi-head attention?",
        "ground_truth": (
            "Multi-head attention performs attention multiple times in parallel "
            "with different linear projections of queries, keys, and values. "
            "The outputs are concatenated and projected to produce the final result."
        ),
    },
    # GenAI (GAN Paper) 
    {
        "question": "What is the minimax game objective in Generative Adversarial Networks?",
        "ground_truth": (
            "GANs are trained using a minimax game framework where the generator G tries "
            "to minimize log(1 - D(G(z))) while the discriminator D tries to maximize the "
            "probability of correctly classifying real and generated data, leading to the "
            "objective function: min_G max_D V(D, G) = E[log D(x)] + E[log(1 - D(G(z)))]."
        ),
    },
    # GenAI (GPT-3 Paper) 
    {
        "question": "What is the parameter size of the largest GPT-3 model evaluated in the paper?",
        "ground_truth": (
            "The largest GPT-3 model has 175 billion parameters. It is an auto-regressive "
            "language model with 96 layers, 96 attention heads, and a context window of 2048 tokens."
        ),
    },
    {
        "question": "How does few-shot learning differ from zero-shot and one-shot learning?",
        "ground_truth": (
            "Few-shot learning provides a few demonstrations of the task (typically 10 to 100) "
            "at test time within the context window. One-shot learning provides exactly one demonstration. "
            "Zero-shot learning provides no examples, only a natural language instruction describing the task."
        ),
    },
    {
        "question": "What are some limitations of GPT-3 mentioned in the paper?",
        "ground_truth": (
            "GPT-3 has limitations including: high cost and difficulty of training, susceptibility "
            "to generating biased or toxic content, lack of active search or retrieval capabilities, "
            "and difficulty with reasoning tasks such as common-sense reasoning or mathematical arithmetic."
        ),
    },
    {
        "question": "What are the theoretical advantages of GANs compared to other generative models like VAEs or Markov chains?",
        "ground_truth": (
            "GANs do not require an explicit probability density function, and the generator is trained without "
            "direct sample-wise comparisons. This allows them to learn complex, sharp distributions without the "
            "blurriness of VAEs and avoids expensive Markov chain sampling."
        ),
    },
    # Shared (Company Handbook) 
    {
        "question": "What is the policy regarding remote work and office attendance?",
        "ground_truth": (
            "Employees are expected to adhere to the company's remote work policy which "
            "outlines working hours, core collaboration periods, and the split between "
            "office presence and remote working days."
        ),
    },
    # RAG (RAG Paper) 
    {
        "question": "What are the two core components of a Retrieval-Augmented Generation (RAG) system?",
        "ground_truth": (
            "A RAG system consists of a retriever (specifically a Dense Passage Retriever, or DPR, "
            "which uses dense vector embeddings to search for relevant passages) and a generator "
            "(a sequence-to-sequence transformer model like BART that synthesizes the retrieved "
            "passages to generate the final text)."
        ),
    },
    {
        "question": "What is the difference between RAG-Sequence and RAG-Token models?",
        "ground_truth": (
            "RAG-Sequence uses the same retrieved document to generate the entire answer sequence. "
            "RAG-Token can retrieve different documents for each token generated, allowing it to "
            "combine information from multiple sources."
        ),
    },
    {
        "question": "On what kind of tasks does RAG achieve state-of-the-art results compared to standard parametric models?",
        "ground_truth": (
            "RAG achieves state-of-the-art results on open-domain question answering, abstractive question "
            "answering, and jeopardy question generation. It generates more factual, specific, and diverse "
            "responses than parametric-only models."
        ),
    },
    {
        "question": "What are the core values and code of conduct expected of employees?",
        "ground_truth": (
            "The code of conduct expects employees to act with integrity, professionalism, "
            "and respect, fostering a collaborative, diverse, and inclusive work environment "
            "free of harassment."
        ),
    },
]


# Combined Prompts 

COMBINED_JUDGE_PROMPT = """You are an expert AI evaluator judging RAG system response quality.
Analyze the following input:
- Question: {question}
- Ground Truth Answer: {ground_truth}
- Retrieved Contexts: {contexts}
- Generated Answer: {answer}

Please evaluate the response based on the following four quality metrics:

1. Faithfulness (Groundedness): Is every claim in the generated answer strictly supported by the retrieved contexts?
2. Answer Relevance: Does the generated answer directly address the user's question completely and without fluff?
3. Context Precision: Out of the retrieved contexts, how much of it was actually relevant and useful for answering the query?
4. Context Recall: Does the retrieved context contain all the necessary facts and details mentioned in the ground truth answer?

For each metric, provide:
- A score from 1 to 5, where:
  5: Excellent / Perfect
  4: Good / Mostly accurate
  3: Moderate / Partially accurate
  2: Poor / Low accuracy
  1: Very Poor / Completely inaccurate
- A brief, one-sentence reasoning.

Provide your output as a single JSON object structured exactly like this:
{{
  "faithfulness": {{
    "score": <int 1-5>,
    "reasoning": "<string reasoning>"
  }},
  "answer_relevance": {{
    "score": <int 1-5>,
    "reasoning": "<string reasoning>"
  }},
  "context_precision": {{
    "score": <int 1-5>,
    "reasoning": "<string reasoning>"
  }},
  "context_recall": {{
    "score": <int 1-5>,
    "reasoning": "<string reasoning>"
  }}
}}

Response JSON:"""


# Helpers 


def parse_combined_judge_output(raw_text: str) -> Dict[str, Any]:
    """Extract JSON object and parse all 4 metrics score/reasoning robustly.

    Ensures all 4 metrics are present and properly formatted to prevent KeyError.
    """
    raw_text = raw_text.strip()
    parsed_data = None

    # 1. Attempt straightforward JSON parse
    try:
        parsed_data = json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    # 2. Attempt markdown JSON block extraction
    if parsed_data is None:
        for marker in ("```json", "```"):
            if marker in raw_text:
                try:
                    block = raw_text.split(marker)[1].split("```")[0].strip()
                    parsed_data = json.loads(block)
                    break
                except Exception:
                    pass

    # 3. Fallback structure
    default_scores = {
        "faithfulness": {
            "score": 3,
            "reasoning": "Fallback score due to parsing error.",
        },
        "answer_relevance": {
            "score": 3,
            "reasoning": "Fallback score due to parsing error.",
        },
        "context_precision": {
            "score": 3,
            "reasoning": "Fallback score due to parsing error.",
        },
        "context_recall": {
            "score": 3,
            "reasoning": "Fallback score due to parsing error.",
        },
    }

    # 4. Attempt regex parsing if JSON parsing failed completely
    if parsed_data is None:
        try:
            import re

            metrics = [
                "faithfulness",
                "answer_relevance",
                "context_precision",
                "context_recall",
            ]
            for metric in metrics:
                metric_block = re.search(rf'"{metric}"\s*:\s*\{{([^}}]+)\}}', raw_text)
                if metric_block:
                    block_content = metric_block.group(1)
                    score_match = re.search(r'"score"\s*:\s*(\d)', block_content)
                    reasoning_match = re.search(
                        r'"reasoning"\s*:\s*"([^"]+)"', block_content
                    )
                    if score_match:
                        default_scores[metric]["score"] = int(score_match.group(1))
                    if reasoning_match:
                        default_scores[metric]["reasoning"] = reasoning_match.group(1)
            parsed_data = default_scores
        except Exception:
            parsed_data = default_scores

    # 5. Normalize and validate keys/values (casing, naming, type safety)
    normalized_scores = {}
    if isinstance(parsed_data, dict):
        for k, v in parsed_data.items():
            norm_k = str(k).lower().strip().replace(" ", "_").replace("-", "_")
            # Map key variations to standard names
            if "faithful" in norm_k:
                norm_k = "faithfulness"
            elif "relevance" in norm_k or "relevancy" in norm_k:
                norm_k = "answer_relevance"
            elif "precision" in norm_k:
                norm_k = "context_precision"
            elif "recall" in norm_k:
                norm_k = "context_recall"

            if isinstance(v, dict):
                score = v.get("score", 3)
                reasoning = v.get("reasoning", "Parsed reasoning.")
                try:
                    score = int(score)
                except Exception:
                    score = 3
                normalized_scores[norm_k] = {
                    "score": score,
                    "reasoning": str(reasoning),
                }
            elif isinstance(v, (int, float)):
                # Flat score format
                normalized_scores[norm_k] = {
                    "score": int(v),
                    "reasoning": "Flat score format parsed.",
                }

    # 6. Ensure all 4 standard keys are present (fill with defaults if missing)
    final_scores = {
        "faithfulness": {
            "score": 3,
            "reasoning": "Fallback due to missing metric in output.",
        },
        "answer_relevance": {
            "score": 3,
            "reasoning": "Fallback due to missing metric in output.",
        },
        "context_precision": {
            "score": 3,
            "reasoning": "Fallback due to missing metric in output.",
        },
        "context_recall": {
            "score": 3,
            "reasoning": "Fallback due to missing metric in output.",
        },
    }

    for metric in final_scores:
        if metric in normalized_scores:
            final_scores[metric] = normalized_scores[metric]

    return final_scores


async def call_groq_with_retry(
    client: AsyncGroq, messages: List[Dict], max_retries: int = 5
) -> str:
    """Execute Groq chat completion with exponential backoff on rate limits."""
    delay = 2.0
    current_judge_model = JUDGE_MODEL_NAME
    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(
                model=current_judge_model,
                messages=messages,
                temperature=0.0,
                max_tokens=400,
            )
            return response.choices[0].message.content
        except Exception as e:
            msg = str(e).lower()

            # If hit by daily token limit (TPD) or daily request limit (RPD), fall back to 8B judge model
            if "tokens per day" in msg or "tpd" in msg or "daily" in msg:
                if current_judge_model == "llama-3.3-70b-versatile":
                    fallback_model = "llama-3.1-8b-instant"
                    print(
                        f"      [Groq Daily Limit] Falling back from {current_judge_model} to {fallback_model}..."
                    )
                    current_judge_model = fallback_model
                    try:
                        response = await client.chat.completions.create(
                            model=current_judge_model,
                            messages=messages,
                            temperature=0.0,
                            max_tokens=400,
                        )
                        return response.choices[0].message.content
                    except Exception as fallback_err:
                        print(f"      [Groq Fallback Failed] {fallback_err}")
                        raise e from fallback_err

            if attempt == max_retries - 1:
                raise

            wait_time = delay
            if "try again in" in msg:
                try:
                    parts = msg.split("try again in")
                    if len(parts) > 1:
                        seconds_str = parts[1].strip().split("s")[0].strip()
                        wait_time = float(seconds_str) + 0.5
                except Exception:
                    pass

            print(
                f"      [Groq Rate Limit] Attempt {attempt + 1} failed. Waiting {wait_time:.1f}s..."
            )
            await asyncio.sleep(wait_time)
            delay *= 2
    return ""


async def evaluate_query_quality_combined(
    client: AsyncGroq,
    question: str,
    answer: str,
    contexts: List[str],
    ground_truth: str,
) -> Dict[str, Dict[str, Any]]:
    """Run all 4 quality metrics in a single Groq request."""
    context_str = "\n---\n".join(contexts) if contexts else "No retrieved context."

    prompt = COMBINED_JUDGE_PROMPT.format(
        question=question,
        answer=answer,
        contexts=context_str,
        ground_truth=ground_truth,
    )

    messages = [
        {
            "role": "system",
            "content": "You are a precise, objective quality assurance evaluator that outputs valid JSON.",
        },
        {"role": "user", "content": prompt},
    ]

    raw_output = await call_groq_with_retry(client, messages)
    return parse_combined_judge_output(raw_output)


# Core Runner 


async def run_evaluation():
    print("=" * 60)
    print("   Sentinel Optimized LLM-as-a-Judge RAG Evaluation (1 Request)")
    print("=" * 60)
    print(f"  API Base   : {API_BASE}")
    print(f"  Seeded User: {EVAL_USER}")
    print(f"  System LLM : {settings.LLM_MODEL_NAME}")
    print(f"  Judge LLM  : {JUDGE_MODEL_NAME}")
    print(f"  Embeddings : {settings.EMBEDDING_MODEL}")
    print(f"  Golden Set : {len(TEST_DATASET)} queries")
    print("=" * 60)

    # 1. Preflight Check
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{API_BASE}/health", timeout=5.0)
            resp.raise_for_status()
            print("  [OK] Backend server is online.")
        except Exception:
            print(f"  [ERROR] Cannot reach backend server at {API_BASE}/health")
            print(
                "  Please make sure your FastAPI app is running (e.g. uvicorn app.main:app)."
            )
            return

    groq_judge = AsyncGroq(api_key=settings.GROQ_API_KEY)
    results = []

    # Headers for Bearer Auth authentication bypass via username
    headers = {
        "Authorization": f"Bearer {EVAL_USER}",
        "Content-Type": "application/json",
    }

    no_info_count = 0
    total_latency_sum = 0.0

    for idx, item in enumerate(TEST_DATASET, start=1):
        q = item["question"]
        gt = item["ground_truth"]

        print(f"\n  [{idx}/{len(TEST_DATASET)}] Query: {q}")

        # Call Backend query pipeline
        t0 = time.perf_counter()
        pipeline_ok = False
        answer = ""
        contexts = []
        decision_mode = "unknown"
        num_candidates = 0

        async with httpx.AsyncClient() as http_client:
            try:
                response = await http_client.post(
                    f"{API_BASE}/eval/query",
                    headers=headers,
                    json={"request_id": f"eval_{int(time.time())}_{idx}", "query": q},
                    timeout=60.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    answer = data.get("answer", "")
                    contexts = data.get("contexts", [])
                    decision_mode = data.get("decision_mode", "unknown")
                    num_candidates = data.get("num_candidates", 0)
                    pipeline_ok = True
                else:
                    print(
                        f"    [FAIL] Backend API returned status {response.status_code}: {response.text}"
                    )
            except Exception as e:
                print(f"    [FAIL] Error querying backend pipeline: {e}")

        elapsed = (time.perf_counter() - t0) * 1000
        total_latency_sum += elapsed

        if not pipeline_ok:
            continue

        print(f"    Decision Mode   : {decision_mode}")
        print(f"    Latency         : {elapsed:.0f}ms")
        print(f"    Answer Snippet  : {answer[:80]}...")

        # If decision mode is no_info, evaluation score is simplified
        if decision_mode == "no_info":
            no_info_count += 1
            scores = {
                "faithfulness": {
                    "score": 5 if "no relevant information" in answer.lower() else 1,
                    "reasoning": "Correctly refused ungrounded answer.",
                },
                "answer_relevance": {
                    "score": 5 if "no relevant information" in answer.lower() else 1,
                    "reasoning": "Directly refused ungrounded query.",
                },
                "context_precision": {
                    "score": 1,
                    "reasoning": "No relevant context chunks found.",
                },
                "context_recall": {
                    "score": 1,
                    "reasoning": "Context failed to retrieve any ground truth facts.",
                },
            }
        else:
            # Run judge evaluations in a single request
            print("    Evaluating quality metrics via Groq (combined request)...")
            try:
                scores = await evaluate_query_quality_combined(
                    groq_judge, q, answer, contexts, gt
                )
            except Exception as e:
                print(f"    [WARN] Error calling Groq Judge: {e}")
                scores = {
                    "faithfulness": {"score": 3, "reasoning": "Failed to judge."},
                    "answer_relevance": {"score": 3, "reasoning": "Failed to judge."},
                    "context_precision": {"score": 3, "reasoning": "Failed to judge."},
                    "context_recall": {"score": 3, "reasoning": "Failed to judge."},
                }

        # Print scores for query
        print(
            f"    -> Faithfulness: {scores['faithfulness']['score'] * 20}% | Relevance: {scores['answer_relevance']['score'] * 20}% | Precision: {scores['context_precision']['score'] * 20}% | Recall: {scores['context_recall']['score'] * 20}%"
        )

        results.append(
            {
                "question": q,
                "ground_truth": gt,
                "answer": answer,
                "contexts": contexts,
                "decision_mode": decision_mode,
                "num_candidates": num_candidates,
                "latency_ms": elapsed,
                "scores": scores,
            }
        )

        # Sleep between loops to respect rate limits
        if idx < len(TEST_DATASET) and DELAY_BETWEEN_QUERIES > 0:
            await asyncio.sleep(DELAY_BETWEEN_QUERIES)

    # Calculate Summary Metrics 
    if not results:
        print("\n  [ERROR] No queries were evaluated successfully.")
        return

    num_queries = len(results)
    avg_latency = total_latency_sum / num_queries
    success_rate = ((num_queries - no_info_count) / num_queries) * 100

    avg_faithfulness = (
        sum(r["scores"]["faithfulness"]["score"] for r in results) / num_queries
    )
    avg_relevance = (
        sum(r["scores"]["answer_relevance"]["score"] for r in results) / num_queries
    )
    avg_precision = (
        sum(r["scores"]["context_precision"]["score"] for r in results) / num_queries
    )
    avg_recall = (
        sum(r["scores"]["context_recall"]["score"] for r in results) / num_queries
    )

    print("\n" + "=" * 60)
    print("                 RAG Evaluation Summary")
    print("=" * 60)
    print(f"  Processed Queries        : {num_queries}")
    print(
        f"  Decision Gate Success    : {num_queries - no_info_count} / {num_queries} ({success_rate:.1f}%)"
    )
    print(f"  Blocked (No-Info)        : {no_info_count} / {num_queries}")
    print(f"  Average Client Latency   : {avg_latency:.0f}ms")
    print("-" * 60)
    print("  Average Quality Scores (Percentage 0 - 100%):")

    def print_metric_bar(name: str, val: float):
        percentage = val * 20.0
        bar_len = int(percentage * 0.4)  # scaling bar size (max 40 blocks)
        bar = "█" * bar_len + "░" * (40 - bar_len)
        print(f"    {name:<18} : {percentage:.1f}%  [{bar}]")

    print_metric_bar("Faithfulness", avg_faithfulness)
    print_metric_bar("Answer Relevance", avg_relevance)
    print_metric_bar("Context Precision", avg_precision)
    print_metric_bar("Context Recall", avg_recall)
    print("=" * 60)

    if no_info_count == num_queries:
        print("\n  [WARNING] All queries returned 'no_info'.")
        print("  Please ingest the target documents before running evaluation.")

    # Save Results to JSON 
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data",
    )
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f"eval_{timestamp}.json")

    report = {
        "timestamp": datetime.now().isoformat(),
        "system_model": settings.LLM_MODEL_NAME,
        "judge_model": JUDGE_MODEL_NAME,
        "embedding_model": settings.EMBEDDING_MODEL,
        "overall_metrics": {
            "num_queries": num_queries,
            "decision_gate_success_rate": round(success_rate, 2),
            "no_info_count": no_info_count,
            "avg_latency_ms": round(avg_latency, 1),
            "avg_faithfulness_pct": round(avg_faithfulness * 20.0, 1),
            "avg_answer_relevance_pct": round(avg_relevance * 20.0, 1),
            "avg_context_precision_pct": round(avg_precision * 20.0, 1),
            "avg_context_recall_pct": round(avg_recall * 20.0, 1),
            "avg_faithfulness": round(avg_faithfulness, 2),
            "avg_answer_relevance": round(avg_relevance, 2),
            "avg_context_precision": round(avg_precision, 2),
            "avg_context_recall": round(avg_recall, 2),
        },
        "details": results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"  Detailed report saved successfully: {output_path}\n")


def main():
    asyncio.run(run_evaluation())


if __name__ == "__main__":
    main()
