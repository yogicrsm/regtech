from agents.framework.state_machine import StateGraph
from agents.nodes.redactor import pii_redactor
from agents.nodes.supervisor import supervisor_router
from agents.nodes.edd import edd_node
from agents.nodes.screening import screening_node
from agents.nodes.qa import qa_node
from agents.nodes.reporter import reporting_node
from agents.nodes.regulatory_qa import regulatory_qa_node
from agents.nodes.impact import impact_node
from agents.nodes.report_batch import batch_report_node
from utils.langfuse_client import new_trace_id, create_trace


def run_qa_pipeline(query: str) -> dict:
    """Entry point for natural-language regulatory Q&A."""
    trace_id = new_trace_id()
    create_trace(trace_id=trace_id, name="QA_Pipeline", input_data={"query": query})

    graph = StateGraph(initial_state={"query": query, "trace_id": trace_id})
    graph.add_node("qa_agent", regulatory_qa_node)
    graph.add_edge("qa_agent", lambda state: None)

    return graph.run("qa_agent")


def run_impact_pipeline(circular_text: str) -> dict:
    """Entry point for regulatory change impact analysis."""
    trace_id = new_trace_id()
    create_trace(trace_id=trace_id, name="Impact_Pipeline", input_data={"circular_text": circular_text[:500]})

    from tools.mcp_registry import mcp_search_tool
    import json

    context_str = mcp_search_tool(query=circular_text[:1000], top_k=5)
    context = json.loads(context_str) if context_str else []

    graph = StateGraph(initial_state={
        "context": context,
        "circular_text": circular_text,
        "trace_id": trace_id
    })
    graph.add_node("impact", impact_node)
    graph.add_edge("impact", lambda state: None)

    return graph.run("impact")


def run_batch_report_pipeline(transactions: list, period: str = "Unspecified") -> dict:
    """Entry point for multi-transaction compliance report generation."""
    trace_id = new_trace_id()
    create_trace(trace_id=trace_id, name="Batch_Report_Pipeline", input_data={
        "transaction_count": len(transactions), "period": period
    })

    graph = StateGraph(initial_state={
        "transactions": transactions,
        "period": period,
        "trace_id": trace_id
    })
    graph.add_node("batch_report", batch_report_node)
    graph.add_edge("batch_report", lambda state: None)

    return graph.run("batch_report")


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