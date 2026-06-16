import json
import logging
from utils.llm_client import call_llm

def qa_node(state):
    logging.info("🔎 QA Specialist: Starting faithfulness validation...")

    screening = state.get("screening_result", {})
    context = state.get("context", []) # Your retrieved regulation chunks
    evidence_score = state.get("evidence_score", 0)

    # 1. Deterministic Citation Check (Do citations exist in context?)
    # We map citation IDs from the screening result against the IDs in the context chunks
    valid_citation_ids = {c["citation"] for c in context}
    cited_ids = screening.get("citations", [])
    
    missing_citations = [c for c in cited_ids if c not in valid_citation_ids]
    
    if missing_citations:
        logging.warning(f"⚠️ QA FAILED: Fabricated citations found: {missing_citations}")
        state["qa_result"] = {"faithful": False, "feedback": f"Invalid citations: {missing_citations}"}
        return state

    # 2. LLM Faithfulness Judge (Are the claims actually in the text?)
    # We pass both the context and the screening reasoning to an LLM judge
    judge_result = call_llm(
        agent_name="QA_Judge",
        prompt_file="qa_judge.yaml", 
        variables={"context": context, "screening": screening},
        trace_id=state.get("trace_id")
    )
    
    # 3. Final decision propagation
    if not judge_result.get("faithful", True) or evidence_score < 0.60:
        logging.warning(f"⚠️ QA FAILED: {judge_result.get('feedback')}")
        state["qa_result"] = {"faithful": False, "feedback": judge_result.get("feedback")}
    else:
        logging.info("✅ QA PASSED: Screening grounded in regulatory evidence.")
        state["qa_result"] = {"faithful": True, "feedback": "Evidence validated."}

    return state