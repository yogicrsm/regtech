import logging


def edd_node(state):

    logging.info(
        "🔍 Enhanced Due Diligence"
    )

    profile = state.get(
        "customer_profile",
        {}
    )

    state["edd_result"] = {
        "edd_required":
            profile.get(
                "risk_rating"
            ) == "HIGH",
        "reason":
            "Customer classified as high risk."
    }

    return state