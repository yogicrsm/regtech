import logging


def reporting_node(state):

    logging.info(
        "📝 Report Specialist"
    )

    screening = state.get(
        "screening_result",
        {}
    )

    qa_result = state.get(
        "qa_result",
        {}
    )

    if not qa_result.get(
        "faithful",
        False
    ):

        state["report"] = {
            "final_decision": "HOLD",
            "executive_summary":
                "Evidence validation failed. Human review required.",
            "regulatory_basis": [],
            "required_actions": [
                "Human compliance review",
                "Re-run retrieval"
            ]
        }

        return state
    

    risk = screening.get(
        "risk_level",
        "LOW"
    )

    if risk == "HIGH":
        decision = "BLOCK"
    elif risk == "MED":
        decision = "HOLD"
    else:
        decision = "ALLOW"

    state["report"] = {
        "final_decision": decision,
        "executive_summary":
            screening.get("reason", ""),
        "regulatory_basis":
            screening.get("citations", []),
        "required_actions": [
            "Archive assessment"
        ]
    }

    return state