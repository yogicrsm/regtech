import ollama
import json

def pii_redactor(state):
    """Local Tier 1: Scrub PII via Llama 3.2."""
    txn = state["txn"]
    prompt = f"Scrub PII (Names, IDs) from: {json.dumps(txn)}. Return valid JSON."
    res = ollama.chat(model='llama3.2', messages=[{'role': 'user', 'content': prompt}], format='json')
    state["redacted_txn"] = json.loads(res['message']['content'])
    return state