import logging


def supervisor_router(state):

    logging.info(
        "🧠 Supervisor: Classifying intent..."
    )

    txn = state.get(
        "txn",
        {}
    )

    amount = txn.get(
        "amount",
        0
    )

    country = txn.get(
        "beneficiary_country",
        ""
    )

    high_risk = {
        "IR",
        "KP",
        "SY"
    }

    if country in high_risk:

        state["next_node"] = "screen"

        state["routing_reason"] = (
            "High-risk jurisdiction"
        )

        return state

    if amount > 1000000:

        state["next_node"] = "screen"

        state["routing_reason"] = (
            "Large value transaction"
        )

        return state

    state["next_node"] = "screen"

    state["routing_reason"] = (
        "Standard compliance screening"
    )

    return state