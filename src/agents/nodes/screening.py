import json
import logging

from utils.llm_client import call_llm
from utils.langfuse_client import create_observation

from tools.mcp_registry import mcp_search_tool
from tools.customer_lookup import get_customer_profile


def screening_node(state):

    logging.info(
        "🕵️ Screening Specialist"
    )

    trace_id = state.get("trace_id")

    redacted_txn = state.get(
        "redacted_txn",
        {}
    )

    raw_txn = state.get(
        "txn",
        {}
    )

    account_id = raw_txn.get(
        "originator_account",
        ""
    )

    customer_str = get_customer_profile(
        customer_id=account_id
    )

    customer_profile = (
        json.loads(customer_str)
        if customer_str
        else {}
    )

    # --------------------------------------------------
    # Customer lookup validation
    # --------------------------------------------------

    if "error" in customer_profile:

        logging.warning(
            f"Customer lookup failed: {customer_profile}"
        )

        customer_profile = {
            "customer_id": account_id,
            "risk_rating": "UNKNOWN",
            "kyc_status": "UNKNOWN",
            "segment": "UNKNOWN"
        }

    # --------------------------------------------------
    # Retrieval query
    # --------------------------------------------------

    logging.info(
        "RAW TXN USED FOR SEARCH:\n%s",
        json.dumps(raw_txn, indent=2)
    )

    retrieval_query = f"""
    Regulatory requirements for a cross-border transaction.

    Amount: {raw_txn.get("amount")}
    Currency: {raw_txn.get("currency")}
    Destination Country: {raw_txn.get("beneficiary_country")}
    Purpose: {raw_txn.get("purpose")}

    Determine:

    - KYC requirements
    - Enhanced Due Diligence requirements
    - High-risk jurisdiction restrictions
    - Transaction monitoring obligations
    - Reporting obligations
    - Whether manual compliance review is required
    """

    logging.info(
        f"🔍 Retrieval Query:\n{retrieval_query}"
    )

    context_str = mcp_search_tool(
        query=retrieval_query,
        top_k=5
    )

    context = (
        json.loads(context_str)
        if context_str
        else []
    )

    logging.info(
        f"📚 Retrieved {len(context)} regulation chunks"
    )

    # --------------------------------------------------
    # Evidence score
    # --------------------------------------------------

    scores = [
        chunk.get("relevance_score", 0)
        for chunk in context
    ]

    evidence_score = (
        sum(scores) / len(scores)
        if scores
        else 0
    )

    state["evidence_score"] = evidence_score

    logging.info(
        f"📊 Evidence Score = {evidence_score:.4f}"
    )

    # --------------------------------------------------
    # State
    # --------------------------------------------------

    state["context"] = context
    state["customer_profile"] = customer_profile

    create_observation(
        trace_id=trace_id,
        name="Regulation_Search",
        input_data=retrieval_query,
        output_data=context,
        metadata={
            "customer_profile": customer_profile,
            "evidence_score": evidence_score,
            "top_k": len(context)
        }
    )

    logging.info(
        "\n===== CONTEXT SENT TO LLM =====\n%s\n===== END CONTEXT =====",
        json.dumps(context, indent=2)
    )

    # --------------------------------------------------
    # Screening LLM
    # --------------------------------------------------

    result = call_llm(
        agent_name="Screening_Specialist",
        prompt_file="screening_v1.yaml",
        variables={
            "transaction": redacted_txn,
            "customer_profile": customer_profile,
            "regulatory_context": context,
            "edd_result": state.get(
                "edd_result",
                {}
            )
        },
        trace_id=trace_id
    )

    # -----------------------------------------
    # Normalize LLM output
    # -----------------------------------------

    if not isinstance(result, dict):
        result = {}

    result.setdefault(
        "compliant",
        False
    )

    result.setdefault(
        "risk_level",
        "MED"
    )

    result.setdefault(
        "reason",
        "No explanation provided."
    )

    # -----------------------------------------
    # Force citations from retrieval
    # -----------------------------------------

    citations = [
        chunk.get("citation")
        for chunk in context
        if chunk.get("citation")
    ]

    evidence = [
        chunk.get("text", "")[:250]
        for chunk in context[:3]
    ]

    if not result.get("citations"):
        result["citations"] = citations

    if not result.get("evidence"):
        result["evidence"] = evidence

    result["evidence_score"] = evidence_score

    logging.info(
        "\n===== SCREENING RESULT =====\n%s\n============================",
        json.dumps(result, indent=2)
    )

    # -----------------------------------------
    # Low-confidence retrieval guardrail
    # -----------------------------------------

    if evidence_score < 0.60:

        logging.warning(
            f"Low evidence score ({evidence_score:.4f})"
        )

        result = {
            "compliant": False,
            "risk_level": "MED",
            "reason":
                "Retrieved evidence confidence too low.",
            "citations": citations,
            "evidence": evidence,
            "evidence_score": evidence_score
        }

    state["screening_result"] = result

    logging.info(
        f"   -> Decision: {result.get('risk_level')}"
    )

    return state