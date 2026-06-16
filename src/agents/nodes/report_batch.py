import json
import logging

from utils.llm_client import call_llm
from utils.langfuse_client import create_observation
from tools.mcp_registry import mcp_search_tool


def _screen_single(txn: dict, trace_id: str) -> dict:
    """Lightweight inline screening for a single transaction in batch mode."""
    query = (
        f"Regulatory requirements for transaction: "
        f"amount={txn.get('amount')} {txn.get('currency', 'USD')}, "
        f"destination={txn.get('beneficiary_country', 'UNKNOWN')}, "
        f"purpose={txn.get('purpose', 'UNKNOWN')}"
    )

    try:
        context_str = mcp_search_tool(query=query, top_k=3)
        context = json.loads(context_str)
    except Exception:
        context = []

    from utils.llm_client import call_llm as _llm
    result = _llm(
        agent_name="Batch_Screener",
        prompt_file="screening_v1.yaml",
        variables={
            "transaction": txn,
            "customer_profile": {},
            "regulatory_context": context,
            "edd_result": {}
        },
        trace_id=trace_id
    )

    if not isinstance(result, dict):
        result = {}

    result.setdefault("compliant", False)
    result.setdefault("risk_level", "MED")
    result.setdefault("reason", "No explanation provided.")
    result.setdefault("citations", [c.get("citation") for c in context if c.get("citation")])

    return {
        "txn_id": txn.get("txn_id", "UNKNOWN"),
        "risk_level": result["risk_level"],
        "compliant": result["compliant"],
        "reason": result["reason"],
        "citations": result["citations"]
    }


def batch_report_node(state):
    """
    Screens a list of transactions and produces an aggregated compliance report.

    Expects state["transactions"]: list[dict]
    Expects state["period"]: str (optional, e.g. "2024-Q2")
    Produces state["batch_report"]: dict
    """
    logging.info("📊 Batch Report Agent: Processing transaction batch...")

    trace_id = state.get("trace_id")
    transactions = state.get("transactions", [])
    period = state.get("period", "Unspecified")

    if not transactions:
        state["batch_report"] = {
            "error": "No transactions provided for batch report."
        }
        return state

    screened = []
    for txn in transactions:
        logging.info(f"   Screening {txn.get('txn_id', '?')}...")
        result = _screen_single(txn, trace_id)
        screened.append(result)

    risk_summary = {"HIGH": 0, "MED": 0, "LOW": 0}
    decision_summary = {"BLOCK": 0, "HOLD": 0, "ALLOW": 0}
    blocked, held = [], []

    for s in screened:
        risk = s["risk_level"]
        risk_summary[risk] = risk_summary.get(risk, 0) + 1

        if risk == "HIGH":
            decision_summary["BLOCK"] += 1
            blocked.append(s["txn_id"])
        elif risk == "MED":
            decision_summary["HOLD"] += 1
            held.append(s["txn_id"])
        else:
            decision_summary["ALLOW"] += 1

    # Ask LLM to synthesize observations and required actions
    synthesis = call_llm(
        agent_name="Batch_Report_Synthesizer",
        prompt_file="batch_report_v1.yaml",
        variables={
            "transactions": screened,
            "period": period
        },
        trace_id=trace_id
    )

    if not isinstance(synthesis, dict):
        synthesis = {}

    # Merge deterministic counts with LLM synthesis
    synthesis["total_transactions"] = len(transactions)
    synthesis["risk_summary"] = risk_summary
    synthesis["decision_summary"] = decision_summary
    synthesis["blocked_transactions"] = blocked
    synthesis["held_transactions"] = held
    synthesis["period"] = period
    synthesis["individual_results"] = screened

    synthesis.setdefault("systemic_observations", [])
    synthesis.setdefault("regulatory_themes", [])
    synthesis.setdefault("required_actions", ["Archive batch report", "Review HIGH-risk transactions"])

    state["batch_report"] = synthesis

    logging.info(
        f"✅ Batch report complete: {len(transactions)} transactions, "
        f"{decision_summary['BLOCK']} blocked, {decision_summary['HOLD']} held"
    )

    if trace_id:
        create_observation(
            trace_id=trace_id,
            name="Batch_Report",
            input_data={"transaction_count": len(transactions), "period": period},
            output_data=synthesis,
            metadata=risk_summary
        )

    return state
