import json
import logging

from tools.hybrid_search import search_regulations


def mcp_search_tool(
    query: str,
    top_k: int = 5
):
    """
    Mandatory real retrieval.
    No silent fallback.
    """

    logging.info(
        f"🛠️ search_regulations(top_k={top_k})"
    )

    results = search_regulations(
        semantic_query=query,
        top_k=top_k
    )

    if not results:
        raise RuntimeError(
            "Regulation retrieval returned zero results."
        )

    logging.info(
        f"✅ Retrieved {len(results)} chunks"
    )

    return json.dumps(
        results,
        ensure_ascii=False
    )