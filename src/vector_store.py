from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings

from src.config import (
    VECTOR_STORE_DIR,
    CORPUS_DIR,
    CONVERTED_MD_DIR,
    UPLOADED_DOCS_COLLECTION,
    AI_ACT_CORPUS_COLLECTION,
    EMBEDDING_PROVIDER,
    OPENAI_EMBEDDING_MODEL,
    LOCAL_EMBEDDING_MODEL,
    OPENAI_API_KEY,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
)
from src.chunking import chunk_text
from src.preprocessing import convert_file_to_markdown, SUPPORTED_EXTENSIONS
from src.corpus_metadata import (
    infer_file_profile,
    enrich_corpus_chunk,
    chroma_metadata_from_corpus_chunk,
    enrich_uploaded_chunk,
    chroma_metadata_from_uploaded_chunk,
)


# ---------------------------------------------------------------------------
# Embedding function helpers
# ---------------------------------------------------------------------------

def _get_embedding_function():
    if EMBEDDING_PROVIDER == "openai":
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
        return OpenAIEmbeddingFunction(
            api_key=OPENAI_API_KEY,
            model_name=OPENAI_EMBEDDING_MODEL,
        )
    else:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        return SentenceTransformerEmbeddingFunction(model_name=LOCAL_EMBEDDING_MODEL)


# ---------------------------------------------------------------------------
# Chroma client (singleton)
# ---------------------------------------------------------------------------

_client: Optional[chromadb.PersistentClient] = None


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=str(VECTOR_STORE_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


# ---------------------------------------------------------------------------
# Collection accessors
# ---------------------------------------------------------------------------

def get_uploaded_collection():
    client = _get_client()
    ef = _get_embedding_function()
    return client.get_or_create_collection(
        name=UPLOADED_DOCS_COLLECTION,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )


def get_corpus_collection():
    client = _get_client()
    ef = _get_embedding_function()
    return client.get_or_create_collection(
        name=AI_ACT_CORPUS_COLLECTION,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )


# ---------------------------------------------------------------------------
# Add session document chunks
# ---------------------------------------------------------------------------

def add_chunks_to_uploaded(chunks: list[dict]) -> None:
    if not chunks:
        return
    enriched = [enrich_uploaded_chunk(c) for c in chunks]
    collection = get_uploaded_collection()
    collection.upsert(
        ids=[c["chunk_id"] for c in enriched],
        documents=[c["text"] for c in enriched],
        metadatas=[chroma_metadata_from_uploaded_chunk(c) for c in enriched],
    )


# ---------------------------------------------------------------------------
# Corpus loader (runs once at startup)
# ---------------------------------------------------------------------------

def load_corpus_to_chroma(force_reload: bool = False, verbose: bool = False) -> int:
    """
    Reads every supported file from corpus/, converts it to Markdown via MarkItDown
    (caching the result under data/converted_markdown/_corpus/), chunks it, and stores
    it in ai_act_corpus_collection. Returns the number of chunks indexed.

    Skips entirely if the collection is already populated unless force_reload=True.
    """
    collection = get_corpus_collection()

    if not force_reload and collection.count() > 0:
        if verbose:
            print(f"[corpus] Already populated ({collection.count()} chunks). Skipping.")
        return collection.count()

    corpus_files = [
        p for p in CORPUS_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    if not corpus_files:
        if verbose:
            print("[corpus] No supported files found in corpus/.")
        return 0

    corpus_md_cache = CONVERTED_MD_DIR / "_corpus"
    corpus_md_cache.mkdir(parents=True, exist_ok=True)

    all_chunks: list[dict] = []

    for src_file in corpus_files:
        if verbose:
            print(f"[corpus] Processing {src_file.name}")

        cached_md = corpus_md_cache / (src_file.stem + ".md")
        if cached_md.exists() and not force_reload:
            text = cached_md.read_text(encoding="utf-8")
        else:
            if src_file.suffix.lower() == ".md":
                text = src_file.read_text(encoding="utf-8")
            else:
                text = convert_file_to_markdown(src_file)
            cached_md.write_text(text, encoding="utf-8")

        if not text.strip():
            if verbose:
                print(f"[corpus]   - empty after conversion, skipped")
            continue

        file_profile = infer_file_profile(src_file.stem)

        raw_chunks = chunk_text(
            text=text,
            chunk_size=CHUNK_SIZE,
            overlap=CHUNK_OVERLAP,
            session_id="",
            filename=src_file.name,
            source_type=file_profile["source_type"],
            document_type="eu_ai_act_corpus",
        )

        enriched_file_chunks: list[dict] = []
        for c in raw_chunks:
            c["chunk_id"] = f"corpus_{src_file.stem}_chunk{c['chunk_index']}"
            enriched_file_chunks.append(enrich_corpus_chunk(c, file_profile))

        if verbose:
            print(f"[corpus]   - {len(enriched_file_chunks)} chunks")
        all_chunks.extend(enriched_file_chunks)

    if not all_chunks:
        return 0

    if force_reload:
        _get_client().delete_collection(AI_ACT_CORPUS_COLLECTION)
        collection = get_corpus_collection()

    BATCH = 200
    for i in range(0, len(all_chunks), BATCH):
        batch = all_chunks[i : i + BATCH]
        collection.upsert(
            ids=[c["chunk_id"] for c in batch],
            documents=[c["text"] for c in batch],
            metadatas=[chroma_metadata_from_corpus_chunk(c) for c in batch],
        )
        if verbose:
            print(f"[corpus]   indexed {min(i + BATCH, len(all_chunks))}/{len(all_chunks)}")

    return len(all_chunks)


def _infer_corpus_source_type(stem: str) -> str:
    return infer_file_profile(stem)["source_type"]


# ---------------------------------------------------------------------------
# Delete session data (call on session end / reset)
# ---------------------------------------------------------------------------

def delete_session_chunks(session_id: str) -> None:
    collection = get_uploaded_collection()
    results = collection.get(where={"session_id": session_id})
    ids = results.get("ids", [])
    if ids:
        collection.delete(ids=ids)
