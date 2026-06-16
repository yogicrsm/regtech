import os
import sys
import json
import ollama
from datetime import datetime
from pathlib import Path

# Allow imports from src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.hybrid_search import search_regulations

JUDGE_MODEL = "llama3.2"

BASE_DIR = Path(__file__).parent.parent.parent
DATASET_PATH = BASE_DIR / "data" / "evaluation" / "test_dataset.json"
REPORTS_DIR = BASE_DIR / "data" / "evaluation" / "reports"


def generate_rag_answer(query: str, context_chunks: list) -> str:
    context_text = "\n".join([c["text"] for c in context_chunks])
    prompt = f"""
Answer the user's question using ONLY the provided regulatory context.

Context:
{context_text}

Question: {query}
"""
    try:
        response = ollama.chat(model=JUDGE_MODEL, messages=[{"role": "user", "content": prompt}])
        return response["message"]["content"]
    except Exception as e:
        return str(e)


def evaluate_faithfulness_relevance(query: str, context: str, answer: str, ground_truth: str) -> dict:
    prompt = f"""
You are an impartial grader evaluating an AI Compliance Assistant.

Evaluate on two metrics (score 1-5):
1. Faithfulness: Is the answer derived entirely from the context, or did it hallucinate?
   (5 = strictly uses context only, 1 = heavily hallucinated)
2. Answer Relevance: Does the answer directly address the query and align with ground truth?
   (5 = perfect match, 1 = completely irrelevant)

Return ONLY valid JSON: {{"faithfulness": int, "relevance": int, "feedback": "string"}}

Query: {query}
Context: {context}
Ground Truth: {ground_truth}
AI Answer: {answer}
"""
    try:
        response = ollama.chat(
            model=JUDGE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            format="json"
        )
        return json.loads(response["message"]["content"])
    except Exception as e:
        return {"faithfulness": 0, "relevance": 0, "feedback": f"Grading failed: {e}"}


def evaluate_context_precision(query: str, context_chunks: list) -> dict:
    """
    Context Precision: what fraction of retrieved chunks are relevant to the query?
    Scored by LLM judge over each chunk individually.
    """
    if not context_chunks:
        return {"context_precision": 0.0, "relevant_count": 0, "total_count": 0}

    relevant = 0
    for chunk in context_chunks:
        prompt = f"""
Is the following regulatory text relevant to answering this query?
Query: {query}
Text: {chunk.get("text", "")[:500]}

Return ONLY valid JSON: {{"relevant": true/false, "reason": "brief reason"}}
"""
        try:
            response = ollama.chat(
                model=JUDGE_MODEL,
                messages=[{"role": "user", "content": prompt}],
                format="json"
            )
            result = json.loads(response["message"]["content"])
            if result.get("relevant", False):
                relevant += 1
        except Exception:
            pass

    precision = relevant / len(context_chunks)
    return {
        "context_precision": round(precision, 4),
        "relevant_count": relevant,
        "total_count": len(context_chunks)
    }


def evaluate_context_recall(query: str, ground_truth: str, context_chunks: list) -> dict:
    """
    Context Recall: what fraction of the ground truth claims are supported by retrieved context?
    """
    context_text = "\n".join([c.get("text", "")[:300] for c in context_chunks])
    prompt = f"""
You are evaluating whether retrieved regulatory context supports the ground truth answer.

Given the retrieved context and the ground truth answer, what fraction of the ground truth
claims can be attributed to (found in) the retrieved context?

Ground Truth: {ground_truth}
Retrieved Context: {context_text}

Return ONLY valid JSON: {{"recall": float_between_0_and_1, "assessment": "brief explanation"}}
"""
    try:
        response = ollama.chat(
            model=JUDGE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            format="json"
        )
        result = json.loads(response["message"]["content"])
        return {
            "context_recall": round(float(result.get("recall", 0)), 4),
            "assessment": result.get("assessment", "")
        }
    except Exception as e:
        return {"context_recall": 0.0, "assessment": f"Recall evaluation failed: {e}"}


def run_evaluation_pipeline():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with open(DATASET_PATH, "r") as f:
        test_cases = json.load(f)

    results_log = []
    totals = {"faithfulness": 0, "relevance": 0, "context_precision": 0.0, "context_recall": 0.0}
    failures = []

    print(f"Starting evaluation on {len(test_cases)} test cases...\n")

    for case in test_cases:
        print(f"[{case['id']}] {case['query'][:60]}...")

        # 1. Retrieval
        context_chunks = search_regulations(semantic_query=case["query"], top_k=3)
        context_text = "\n".join([c["text"] for c in context_chunks])

        # 2. Generation
        ai_answer = generate_rag_answer(case["query"], context_chunks)

        # 3. Faithfulness + Relevance
        print("   Scoring faithfulness and relevance...")
        scores = evaluate_faithfulness_relevance(case["query"], context_text, ai_answer, case["ground_truth"])

        # 4. Context Precision
        print("   Scoring context precision...")
        precision_result = evaluate_context_precision(case["query"], context_chunks)

        # 5. Context Recall
        print("   Scoring context recall...")
        recall_result = evaluate_context_recall(case["query"], case["ground_truth"], context_chunks)

        faith = scores.get("faithfulness", 0)
        rel = scores.get("relevance", 0)
        prec = precision_result.get("context_precision", 0.0)
        rec = recall_result.get("context_recall", 0.0)

        totals["faithfulness"] += faith
        totals["relevance"] += rel
        totals["context_precision"] += prec
        totals["context_recall"] += rec

        if faith < 3 or rel < 3:
            failures.append({"id": case["id"], "query": case["query"], "scores": scores})

        result_entry = {
            "id": case["id"],
            "query": case["query"],
            "jurisdiction": case.get("jurisdiction"),
            "regulation": case.get("regulation"),
            "ai_answer": ai_answer[:300],
            "scores": {
                "faithfulness": faith,
                "relevance": rel,
                "context_precision": prec,
                "context_recall": rec,
            },
            "feedback": scores.get("feedback", ""),
            "precision_detail": precision_result,
            "recall_detail": recall_result,
        }
        results_log.append(result_entry)

        print(
            f"   Faithfulness={faith}/5 | Relevance={rel}/5 | "
            f"Precision={prec:.2f} | Recall={rec:.2f}\n"
        )

    n = len(test_cases)
    avg = {k: round(v / n, 4) for k, v in totals.items()}

    print("=== FINAL EVALUATION REPORT ===")
    print(f"Total Test Cases   : {n}")
    print(f"Avg Faithfulness   : {avg['faithfulness']:.2f} / 5.0")
    print(f"Avg Relevance      : {avg['relevance']:.2f} / 5.0")
    print(f"Avg Context Precision: {avg['context_precision']:.4f}")
    print(f"Avg Context Recall   : {avg['context_recall']:.4f}")
    print(f"Failures (<3/5)    : {len(failures)}")

    report = {
        "run_timestamp": datetime.now().isoformat(),
        "total_test_cases": n,
        "average_scores": avg,
        "failure_count": len(failures),
        "failures": failures,
        "per_question": results_log,
    }

    report_path = REPORTS_DIR / f"eval_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nDetailed report saved to {report_path}")
    return report


if __name__ == "__main__":
    run_evaluation_pipeline()
