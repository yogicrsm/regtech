import ollama
import json
import logging

def impact_node(state):
    """Layer 5 Agent: Cross-references regulation changes to internal policy."""
    logging.info("⚖️  Impact Specialist: Analyzing downstream policy impact...")
    
    context = state.get("context", [])
    
    prompt = f"""
    Given this regulation: {json.dumps(context)}, 
    does this represent a new restriction that requires a policy update?
    Return strictly valid JSON: {{"impact": "NONE/MINOR/MAJOR", "needs_policy_update": bool}}
    """
    
    try:
        res = ollama.chat(model='llama3.2', messages=[{'role': 'user', 'content': prompt}], format='json')
        state["impact_result"] = json.loads(res['message']['content'])
    except Exception as e:
        logging.warning(f"⚠️ Impact LLM failed: {e}")
        state["impact_result"] = {"impact": "UNKNOWN", "needs_policy_update": False}
        
    return state
