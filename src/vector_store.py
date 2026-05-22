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
    collection = get_uploaded_collection()
    collection.upsert(
        ids=[c["chunk_id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        metadatas=[
            {
                "session_id": c.get("session_id", ""),
                "filename": c.get("filename", ""),
                "source_type": c.get("source_type", "uploaded_document"),
                "document_type": c.get("document_type", "general_document"),
                "chunk_index": c.get("chunk_index", 0),
            }
            for c in chunks
        ],
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

        source_type = _infer_corpus_source_type(src_file.stem)
        title = _infer_corpus_title(src_file.stem)

        raw_chunks = chunk_text(
            text=text,
            chunk_size=CHUNK_SIZE,
            overlap=CHUNK_OVERLAP,
            session_id="",
            filename=src_file.name,
            source_type=source_type,
            document_type="eu_ai_act_corpus",
        )

        for c in raw_chunks:
            c["chunk_id"] = f"corpus_{src_file.stem}_chunk{c['chunk_index']}"
            c["title"] = title
            c["section"] = _infer_corpus_section(c["text"])

        if verbose:
            print(f"[corpus]   - {len(raw_chunks)} chunks")
        all_chunks.extend(raw_chunks)

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
            metadatas=[
                {
                    "source_type": c.get("source_type", "regulation"),
                    "document_type": c.get("document_type", "eu_ai_act_corpus"),
                    "filename": c.get("filename", ""),
                    "title": c.get("title", "EU AI Act"),
                    "section": c.get("section", ""),
                    "chunk_index": c.get("chunk_index", 0),
                }
                for c in batch
            ],
        )
        if verbose:
            print(f"[corpus]   indexed {min(i + BATCH, len(all_chunks))}/{len(all_chunks)}")

    return len(all_chunks)


def _infer_corpus_source_type(stem: str) -> str:
    stem_lower = stem.lower()
    if "guideline" in stem_lower or "guidance" in stem_lower:
        return "official_guidance"
    return "regulation"


def _infer_corpus_title(stem: str) -> str:
    stem_lower = stem.lower()
    if "prohibited" in stem_lower:
        return "Commission Guidelines on Prohibited AI Practices"
    if "definition" in stem_lower and "system" in stem_lower:
        return "Commission Guidelines on the Definition of an AI System"
    if "ai_act" in stem_lower or "1689" in stem_lower:
        return "EU AI Act (Regulation 2024/1689)"
    return stem.replace("_", " ")


def _infer_corpus_section(text: str) -> str:
    import re
    match = re.search(r"(Article\s+\d+|Annex\s+[IVX]+|Chapter\s+[IVX]+|Recital\s+\d+)", text, re.IGNORECASE)
    return match.group(0) if match else ""


# ---------------------------------------------------------------------------
# Delete session data (call on session end / reset)
# ---------------------------------------------------------------------------

def delete_session_chunks(session_id: str) -> None:
    collection = get_uploaded_collection()
    results = collection.get(where={"session_id": session_id})
    ids = results.get("ids", [])
    if ids:
        collection.delete(ids=ids)
