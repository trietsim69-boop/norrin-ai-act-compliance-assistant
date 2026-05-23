from src.config import TOP_K, MAX_UPLOADED_CONTEXT_CHUNKS, MAX_CORPUS_CONTEXT_CHUNKS
from src.vector_store import get_uploaded_collection, get_corpus_collection

# ---------------------------------------------------------------------------
# Standard retrieval queries used for every assessment
# ---------------------------------------------------------------------------

STANDARD_QUERIES = [
    "What is the purpose and function of the AI system?",
    "What inputs, outputs, recommendations, predictions, decisions, or content does the system produce?",
    "Does this technology meet the AI Act Article 3 definition of an AI system, including machine-based operation, autonomy, objectives, inputs, and inferred outputs?",
    "Could this technology be outside the AI system definition because it is basic data processing, classical heuristics, simple prediction, or mathematical optimization?",
    "Who are the affected persons or subjects of this AI system?",
    "What sector, domain, deployment context, and intended use does this AI system operate in?",
    "What role does the organization have under the AI Act: provider, deployer, importer, distributor, product manufacturer, or authorized representative?",
    "Does a human make the final decision or does the AI output determine outcomes?",
    "Does this system manipulate, deceive, use subliminal techniques, or materially distort a person's behavior under Article 5(1)(a)?",
    "Does this system exploit vulnerabilities based on age, disability, or social or economic situation under Article 5(1)(b)?",
    "Does this system perform social scoring or evaluate trustworthiness based on social behavior or personal characteristics under Article 5(1)(c)?",
    "Does this system assess or predict criminal risk, predictive policing, or likelihood of committing a criminal offence under Article 5(1)(d)?",
    "Does this system use untargeted scraping of facial images from the internet or CCTV to build or expand facial recognition databases under Article 5(1)(e)?",
    "Does this system involve emotion recognition in workplace or education contexts under Article 5(1)(f)?",
    "Does this system use biometric categorisation to infer sensitive attributes such as race, political opinions, trade union membership, religion, sex life, or sexual orientation under Article 5(1)(g)?",
    "Does this system involve real-time remote biometric identification in publicly accessible spaces for law enforcement under Article 5(1)(h)?",
    "Does this system involve biometrics, biometric identification, biometric verification, or biometric categorisation under Annex III area 1?",
    "Does this system affect critical infrastructure, safety components, traffic, water, gas, heating, or electricity under Annex III area 2?",
    "Does this system relate to education, vocational training, admission, assessment, or student monitoring under Annex III area 3?",
    "Does this system relate to employment, recruitment, or worker management?",
    "Does this system affect access to essential private services, essential public services, benefits, credit, insurance, or emergency services under Annex III area 5?",
    "Does this system support law enforcement decisions, evidence evaluation, profiling, or risk assessment under Annex III area 6?",
    "Does this system support migration, asylum, border control, visa, residence permit, or security risk decisions under Annex III area 7?",
    "Does this system support administration of justice, democratic processes, judicial decisions, legal interpretation, elections, or voting behavior under Annex III area 8?",
    "Does this involve a chatbot or conversational AI interacting with humans?",
    "Does this involve AI-generated content, synthetic audio, synthetic image, synthetic video, deepfake, or labelling obligations under Article 50?",
    "Is a third-party LLM or general-purpose AI model used in this system?",
    "What documentation, risk management, logging, transparency, human oversight, monitoring, accountability, accuracy, robustness, or cybersecurity measures are described?",
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

    return _format_results(results, evidence_source="uploaded")


def retrieve_ai_act_context(
    query: str,
    top_k: int = TOP_K,
) -> list[dict]:
    collection = get_corpus_collection()
    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, collection.count()),
    )

    return _format_results(results, evidence_source="corpus")


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

    # Sort by relevance score (lower distance = more relevant)
    uploaded_chunks.sort(key=lambda x: x.get("distance", 1.0))
    corpus_chunks.sort(key=lambda x: x.get("distance", 1.0))

    return {
        "uploaded_chunks": uploaded_chunks[:MAX_UPLOADED_CONTEXT_CHUNKS],
        "corpus_chunks": corpus_chunks[:MAX_CORPUS_CONTEXT_CHUNKS],
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _format_results(results: dict, evidence_source: str) -> list[dict]:
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
                "evidence_source": evidence_source,
                **meta,
            }
        )

    return formatted
