from src.config import TOP_K
from src.vector_store import get_uploaded_collection, get_corpus_collection
from src.corpus_metadata import infer_retrieval_targets

# ---------------------------------------------------------------------------
# Standard retrieval queries used for every assessment
# ---------------------------------------------------------------------------

STANDARD_QUERIES = [
    "What is the purpose and function of the AI system?",
    "Who are the affected persons or subjects of this AI system?",
    "Does this system relate to employment, recruitment, or worker management?",
    "Does this involve a chatbot or conversational AI interacting with humans?",
    "Does this involve emotion recognition, biometric data, or facial analysis?",
    "Is a third-party LLM or general-purpose AI model used in this system?",
    "What sector or domain does this AI system operate in?",
    "Does a human make the final decision or does the AI output determine outcomes?",
]


# ---------------------------------------------------------------------------
# Core retrieval functions
# ---------------------------------------------------------------------------

def retrieve_uploaded_context(
    query: str,
    session_id: str,
    top_k: int = TOP_K,
) -> list[dict]:
    collection = get_uploaded_collection()
    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, collection.count()),
        where={"session_id": session_id},
    )

    return _format_results(results)


def retrieve_ai_act_context(
    query: str,
    top_k: int = TOP_K,
    where: dict | None = None,
) -> list[dict]:
    collection = get_corpus_collection()
    if collection.count() == 0:
        return []

    kwargs: dict = {
        "query_texts": [query],
        "n_results": min(top_k, collection.count()),
    }
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)

    return _format_results(results)


def retrieve_combined_context(
    queries: list[str],
    session_id: str,
    top_k: int = TOP_K,
) -> dict:
    """
    Run multiple queries against both collections and return deduplicated results.
    Returns a dict with 'uploaded_chunks' and 'corpus_chunks'.
    """
    if not queries:
        queries = STANDARD_QUERIES

    seen_uploaded: set[str] = set()
    seen_corpus: set[str] = set()
    uploaded_chunks: list[dict] = []
    corpus_chunks: list[dict] = []

    for q in queries:
        for chunk in retrieve_uploaded_context(q, session_id, top_k=top_k):
            cid = chunk["chunk_id"]
            if cid not in seen_uploaded:
                seen_uploaded.add(cid)
                uploaded_chunks.append(chunk)

        for chunk in retrieve_ai_act_context(q, top_k=top_k):
            cid = chunk["chunk_id"]
            if cid not in seen_corpus:
                seen_corpus.add(cid)
                corpus_chunks.append(chunk)

    # Metadata-targeted corpus retrieval from uploaded-document signals
    for target in infer_retrieval_targets(uploaded_chunks):
        for chunk in retrieve_ai_act_context(
            target["query"],
            top_k=top_k,
            where=target.get("where"),
        ):
            cid = chunk["chunk_id"]
            if cid not in seen_corpus:
                seen_corpus.add(cid)
                corpus_chunks.append(chunk)

    # Sort by relevance score (lower distance = more relevant)
    uploaded_chunks.sort(key=lambda x: x.get("distance", 1.0))
    corpus_chunks.sort(key=lambda x: x.get("distance", 1.0))

    return {
        "uploaded_chunks": uploaded_chunks,
        "corpus_chunks": corpus_chunks,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _format_results(results: dict) -> list[dict]:
    formatted = []
    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for chunk_id, text, meta, dist in zip(ids, documents, metadatas, distances):
        formatted.append(
            {
                "chunk_id": chunk_id,
                "text": text,
                "distance": dist,
                **meta,
            }
        )

    return formatted
