import re


def rerank(query: str, results: list, top_k: int, k: int = 60) -> list:
    """
    Reciprocal Rank Fusion over two signals:
      - vector_rank: position in the original cosine-similarity ordering
      - keyword_rank: position when sorted by query-term density in raw_text

    RRF formula: score = Σ 1 / (k + rank_i)
    α=0.6 weight on vector rank, β=0.4 on keyword rank.
    """
    if not results:
        return results

    query_tokens = set(re.findall(r"\w+", query.lower()))

    def keyword_density(text: str) -> float:
        if not query_tokens:
            return 0.0
        text_tokens = re.findall(r"\w+", text.lower())
        if not text_tokens:
            return 0.0
        hits = sum(1 for t in text_tokens if t in query_tokens)
        return hits / len(text_tokens)

    # Keyword scores → rank
    scored = [(i, keyword_density(r.get("text", ""))) for i, r in enumerate(results)]
    keyword_order = [i for i, _ in sorted(scored, key=lambda x: x[1], reverse=True)]
    keyword_rank = {orig_idx: rank for rank, orig_idx in enumerate(keyword_order)}

    # RRF
    for vector_rank, result in enumerate(results):
        kw_rank = keyword_rank[vector_rank]
        rrf_score = 0.6 * (1 / (k + vector_rank)) + 0.4 * (1 / (k + kw_rank))
        result["rerank_score"] = round(rrf_score, 6)

    reranked = sorted(results, key=lambda r: r["rerank_score"], reverse=True)
    return reranked[:top_k]
