from tools.mcp_registry import mcp_search_tool
import logging

def tool_executor_node(state):
    """The Hands of the ReAct Loop. Executes tools and records observations."""
    decision = state.get("current_decision", {})
    action = decision.get("action")
    action_input = decision.get("action_input")
    
    logging.info(f"🛠️  Executing Tool: {action}...")
    
    observation = "Tool not found."
    if action == "search_regulations":
        # Call the MCP Tool
        observation = mcp_search_tool(query=str(action_input), top_k=2)
    
    # Log the observation back into the scratchpad
    state["scratchpad"].append({
        "role": "Environment",
        "observation": observation
    })
    
    logging.info(f"👀 Observation recorded. Handing control back to Agent.")
    return state