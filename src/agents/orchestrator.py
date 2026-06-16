from agents.framework.state_machine import StateGraph
from agents.nodes.redactor import pii_redactor
from agents.nodes.supervisor import supervisor_router
from agents.nodes.edd import edd_node
from agents.nodes.screening import screening_node
from agents.nodes.qa import qa_node
from agents.nodes.reporter import reporting_node
from utils.langfuse_client import new_trace_id, create_trace

def run_compliance_pipeline(transaction):
    trace_id = new_trace_id()
    create_trace(
        trace_id=trace_id,
        name="Compliance_Pipeline",
        input_data=transaction
    )

    # Initial state carries the transaction, trace context, and container for audit results
    graph = StateGraph(
        initial_state={
            "txn": transaction,
            "trace_id": trace_id,
            "screening_result": None,
            "context": None,
            "qa_result": None
        }
    )

    # -------------------------
    # Node Definitions
    # -------------------------
    graph.add_node("redact", pii_redactor)
    graph.add_node("supervise", supervisor_router)
    graph.add_node("edd", edd_node)
    graph.add_node("screen", screening_node) # Now returns {screening_result, context}
    graph.add_node("qa", qa_node)             # Performs faithfulness check
    graph.add_node("report", reporting_node)

    # -------------------------
    # Flow Logic
    # -------------------------
    graph.add_edge("redact", lambda state: "supervise")
    
    graph.add_edge("supervise", lambda state: state.get("next_node", "screen"))
    
    graph.add_edge("edd", lambda state: "screen")
    
    graph.add_edge("screen", lambda state: "qa")
    
    # Conditional edge: If QA faithfulness fails, we can force a HOLD/REPORT
    graph.add_edge(
        "qa", 
        lambda state: "report" # Report consumes the state (including qa_result)
    )
    
    graph.add_edge("report", lambda state: None)

    return graph.run("redact")