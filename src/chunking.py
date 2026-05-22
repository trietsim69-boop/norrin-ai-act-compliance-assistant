import re
from pathlib import Path

from src.config import CHUNK_SIZE, CHUNK_OVERLAP


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
    session_id: str = "",
    filename: str = "",
    source_type: str = "uploaded_document",
    document_type: str = "general_document",
) -> list[dict]:
    """
    Split text into overlapping chunks and attach metadata to each.
    Splits preferably at paragraph or sentence boundaries.
    """
    text = text.strip()
    if not text:
        return []

    # Split on paragraph breaks first, then fall back to sentence breaks
    paragraphs = re.split(r"\n{2,}", text)

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current) + len(para) + 1 <= chunk_size:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            # If a single paragraph is larger than chunk_size, split by sentences
            if len(para) > chunk_size:
                sentences = re.split(r"(?<=[.!?])\s+", para)
                sentence_buffer = ""
                for sent in sentences:
                    if len(sentence_buffer) + len(sent) + 1 <= chunk_size:
                        sentence_buffer = (sentence_buffer + " " + sent).strip()
                    else:
                        if sentence_buffer:
                            chunks.append(sentence_buffer)
                        sentence_buffer = sent
                if sentence_buffer:
                    chunks.append(sentence_buffer)
                current = ""
            else:
                current = para

    if current:
        chunks.append(current)

    # Apply overlap: prepend the tail of the previous chunk to each chunk
    result: list[dict] = []
    stem = Path(filename).stem if filename else "doc"

    for idx, chunk_text_content in enumerate(chunks):
        if idx > 0 and overlap > 0:
            prev_tail = chunks[idx - 1][-overlap:]
            chunk_text_content = prev_tail + "\n\n" + chunk_text_content

        chunk_id_parts = [p for p in [session_id, stem, f"chunk{idx}"] if p]
        chunk_id = "_".join(chunk_id_parts)

        result.append(
            {
                "chunk_id": chunk_id,
                "session_id": session_id,
                "filename": filename,
                "source_type": source_type,
                "document_type": document_type,
                "text": chunk_text_content,
                "chunk_index": idx,
                "page": None,
            }
        )

    return result


def chunk_document(doc: dict) -> list[dict]:
    """
    Convenience wrapper that accepts a preprocessing result dict
    (as returned by process_uploaded_files) and returns chunks.
    """
    md_path = doc.get("markdown_path")
    if not md_path:
        return []

    text = Path(md_path).read_text(encoding="utf-8")

    return chunk_text(
        text=text,
        session_id=doc.get("session_id", ""),
        filename=doc.get("filename", ""),
        source_type="uploaded_document",
        document_type=doc.get("document_type", "general_document"),
    )
