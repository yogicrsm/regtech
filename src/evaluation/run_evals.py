import os
import json
import ollama
from datetime import datetime

# Import your tools
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.hybrid_search import search_regulations

# LLM-as-a-Judge Config
JUDGE_MODEL = "llama3.2"

def generate_rag_answer(query: str, context_chunks: list) -> str:
    """Uses the local model to answer the question based on retrieved context."""
    context_text = "\n".join([c['text'] for c in context_chunks])
    
    prompt = f"""
    Answer the user's question using ONLY the provided regulatory context.
    
    Context: {context_text}
    Question: {query}
    """
    try:
        response = ollama.chat(model=JUDGE_MODEL, messages=[{'role': 'user', 'content': prompt}])
        return response['message']['content']
    except Exception as e:
        return str(e)

def evaluate_metrics(query: str, context: str, answer: str, ground_truth: str) -> dict:
    """Uses LLM-as-a-judge to score Faithfulness and Relevance."""
    print("   ⚖️ Running LLM-as-a-Judge grading...")
    
    prompt = f"""
    You are an impartial grader evaluating an AI Compliance Assistant.
    
    Evaluate the AI's answer based on two metrics:
    1. Faithfulness (1-5): Is the answer entirely derived from the context, or did it hallucinate external information? (5 = strictly used context).
    2. Answer Relevance (1-5): Does the answer directly address the user's query and match the ground truth? (5 = perfect match).
    
    Return ONLY a valid JSON object: {{"faithfulness": int, "relevance": int, "feedback": "string"}}
    
    Query: {query}
    Context: {context}
    Ground Truth: {ground_truth}
    AI Answer: {answer}
    """
    try:
        response = ollama.chat(model=JUDGE_MODEL, messages=[{'role': 'user', 'content': prompt}], format='json')
        return json.loads(response['message']['content'])
    except Exception as e:
        return {"faithfulness": 0, "relevance": 0, "feedback": f"Grading failed: {e}"}

def run_evaluation_pipeline():
    dataset_path = "/Users/ryogeshwaran/workpace/regtech/data/evaluation/test_dataset.json"
    
    with open(dataset_path, "r") as f:
        test_cases = json.load(f)
        
    results_log = []
    total_faithfulness = 0
    total_relevance = 0
    
    print(f"🚀 Starting Custom RAGAS-style Evaluation on {len(test_cases)} test cases...\n")
    
    for case in test_cases:
        print(f"Testing: {case['id']} - {case['query'][:50]}...")
        
        # 1. Retrieval (Context Precision check)
        context_chunks = search_regulations(semantic_query=case['query'], top_k=2)
        context_text = "\n".join([c['text'] for c in context_chunks])
        
        # 2. Generation
        ai_answer = generate_rag_answer(case['query'], context_chunks)
        
        # 3. Evaluation
        scores = evaluate_metrics(case['query'], context_text, ai_answer, case['ground_truth'])
        
        total_faithfulness += scores.get('faithfulness', 0)
        total_relevance += scores.get('relevance', 0)
        
        results_log.append({
            "id": case['id'],
            "query": case['query'],
            "scores": scores
        })
        print(f"   ✅ Score - Faithfulness: {scores.get('faithfulness')}/5 | Relevance: {scores.get('relevance')}/5\n")
        
    # Generate Final Report
    avg_faith = total_faithfulness / len(test_cases)
    avg_rel = total_relevance / len(test_cases)
    
    print("📊 === FINAL EVALUATION REPORT ===")
    print(f"Total Test Cases: {len(test_cases)}")
    print(f"Average Faithfulness Score: {avg_faith:.2f} / 5.0")
    print(f"Average Relevance Score: {avg_rel:.2f} / 5.0")
    
    # Save report
    os.makedirs("/Users/ryogeshwaran/workpace/regtech/data/evaluation/reports", exist_ok=True)
    report_path = f"/Users/ryogeshwaran/workpace/regtech/data/evaluation/reports/eval_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w") as f:
        json.dump(results_log, f, indent=2)
    print(f"\n💾 Detailed report saved to {report_path}")

if __name__ == "__main__":
    run_evaluation_pipeline()