import re

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

# Always run these against both collections
_CORE_QUERIES = [
    STANDARD_QUERIES[0],  # purpose
    STANDARD_QUERIES[1],  # affected persons
    STANDARD_QUERIES[6],  # sector
    STANDARD_QUERIES[7],  # human oversight / final decision
]

_CONDITIONAL_CORPUS_QUERIES: list[tuple[tuple[str, ...], str]] = [
    (("recruit", "hiring", "candidate", "employment", "worker", "hr", "applicant", "screening"), STANDARD_QUERIES[2]),
    (("chatbot", "conversational", "customer support", "virtual assistant"), STANDARD_QUERIES[3]),
    (("emotion", "facial", "biometric", "affect", "mood"), STANDARD_QUERIES[4]),
    (("gpt", "llm", "large language model", "general purpose", "claude", "openai", "foundation"), STANDARD_QUERIES[5]),
]


def select_assessment_queries(uploaded_chunks: list[dict]) -> list[str]:
    """
    Build a scoped query list from uploaded evidence signals.

    Core queries always run. Domain-specific corpus queries run only when
    uploaded text suggests that domain (avoids flooding PM cases with HR law).
    """
    blob = " ".join(c.get("text", "") for c in uploaded_chunks).lower()
    queries = list(_CORE_QUERIES)
    for keywords, query in _CONDITIONAL_CORPUS_QUERIES:
        if any(re.search(rf"\b{re.escape(kw)}\b", blob) for kw in keywords):
            if query not in queries:
                queries.append(query)
    return queries


def select_corpus_queries(uploaded_chunks: list[dict]) -> list[str]:
    """Queries used for corpus-only retrieval (scoped to uploaded signals)."""
    return select_assessment_queries(uploaded_chunks)


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

    Uploaded collection: all provided queries (or STANDARD_QUERIES).
    Corpus collection: scoped queries derived from uploaded evidence signals
    so unrelated domains (e.g. HR Annex III) are not retrieved for every case.
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

    corpus_queries = select_corpus_queries(uploaded_chunks)

    for q in corpus_queries:
        for chunk in retrieve_ai_act_context(q, top_k=top_k):
            cid = chunk["chunk_id"]
            if cid not in seen_corpus:
                seen_corpus.add(cid)
                corpus_chunks.append(chunk)

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
