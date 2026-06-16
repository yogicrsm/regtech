import json
import logging

from utils.llm_client import call_llm
from utils.langfuse_client import create_observation
from tools.mcp_registry import mcp_search_tool


def regulatory_qa_node(state):
    """
    Answers a natural-language regulatory question using RAG.

    Expects state["query"]: str
    Produces state["qa_answer"]: dict with answer, citations, confidence
    """
    logging.info("📖 Regulatory Q&A Agent: Processing query...")

    trace_id = state.get("trace_id")
    query = state.get("query", "")

    if not query.strip():
        state["qa_answer"] = {
            "answer": "No query provided.",
            "citations": [],
            "source_documents": [],
            "confidence": "LOW",
            "coverage_note": "Empty query received."
        }
        return state

    # Retrieve relevant regulatory context
    try:
        context_str = mcp_search_tool(query=query, top_k=5)
        context = json.loads(context_str)
    except Exception as e:
        logging.warning(f"Retrieval failed: {e}")
        context = []

    logging.info(f"📚 Retrieved {len(context)} chunks for Q&A")

    if trace_id:
        create_observation(
            trace_id=trace_id,
            name="QA_Retrieval",
            input_data=query,
            output_data=context,
            metadata={"top_k": len(context)}
        )

    # Generate cited answer
    result = call_llm(
        agent_name="QA_Agent",
        prompt_file="qa_v1.yaml",
        variables={"query": query, "context": context},
        trace_id=trace_id
    )

    if not isinstance(result, dict):
        result = {}

    result.setdefault("answer", "Unable to generate answer.")
    result.setdefault("citations", [c.get("citation") for c in context if c.get("citation")])
    result.setdefault("source_documents", [c.get("document") for c in context if c.get("document")])
    result.setdefault("confidence", "LOW")
    result.setdefault("coverage_note", "")
    result["retrieved_context"] = context

    state["qa_answer"] = result

    logging.info(f"✅ Q&A complete. Confidence: {result.get('confidence')}")
    return state
