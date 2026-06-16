import json
import ollama
import logging

def screening_react_node(state):
    """The Autonomous Brain of the ReAct Loop."""
    txn = state.get("redacted_txn", {})
    scratchpad = state.get("scratchpad", [])
    
    # The ReAct Prompt Template
    prompt = f"""
    You are a RegTech Compliance Agent. Your job is to screen this transaction: {json.dumps(txn)}
    
    You have access to the following tools:
    - "search_regulations": Searches the bitemporal database for compliance rules. Input should be a search query string.
    - "FINAL_ANSWER": Use this when you have enough information to make a decision. Input should be your final JSON report.
    
    Here is what you have done so far (Scratchpad):
    {json.dumps(scratchpad, indent=2)}
    
    Based on the scratchpad, what is your next step? 
    You MUST respond in strictly valid JSON with exactly these keys:
    {{"thought": "Your reasoning for what to do next", "action": "tool_name", "action_input": "the input for the tool"}}
    """
    
    logging.info("🧠 Agent is Thinking...")
    res = ollama.chat(model='llama3.2', messages=[{'role': 'user', 'content': prompt}], format='json')
    
    try:
        decision = json.loads(res['message']['content'])
        state["current_decision"] = decision
        
        # Log the thought to the scratchpad so it remembers next loop
        state.setdefault("scratchpad", []).append({
            "role": "Agent", 
            "thought": decision.get("thought"), 
            "action": decision.get("action"), 
            "input": decision.get("action_input")
        })
        
        logging.info(f"   Thought: {decision.get('thought')}")
        logging.info(f"   Action: {decision.get('action')} ({decision.get('action_input')})")
        
    except Exception as e:
        logging.error(f"ReAct parsing failed: {e}")
        state["current_decision"] = {"action": "FINAL_ANSWER", "action_input": "Error: Parsing failed."}
        
    return state