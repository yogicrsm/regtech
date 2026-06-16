from agents.framework.state_machine import StateGraph
from agents.nodes.redactor import pii_redactor
from agents.nodes.supervisor import supervisor_router
from agents.nodes.screening import screening_node
from agents.nodes.reporter import reporting_node
from agents.nodes.qa import qa_node
from agents.nodes.impact import impact_node

def run_compliance_pipeline(transaction):
    graph = StateGraph(initial_state={"txn": transaction})
    
    # Register all nodes
    graph.add_node("redact", pii_redactor)
    graph.add_node("supervise", supervisor_router)
    graph.add_node("screen", screening_node)
    graph.add_node("qa", qa_node)
    graph.add_node("impact", impact_node)
    graph.add_node("report", reporting_node)
    
    # Define Topology (Edges)
    graph.add_edge("redact", lambda state: "supervise")
    graph.add_edge("supervise", lambda state: state.get('next_node', 'screen')) # Default to screen if routing fails
    
    # Screening -> QA -> Impact -> Report
    graph.add_edge("screen", lambda state: "qa")
    graph.add_edge("qa", lambda state: "impact")
    graph.add_edge("impact", lambda state: "report")
    graph.add_edge("report", lambda state: None) 
    
    return graph.run("redact")