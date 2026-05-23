"""
Resolve chunk_id citations into human-readable evidence cards.

Three resolver layers:
1. Chroma lookup fetches document text and stored metadata by chunk_id.
2. Evidence cache matches chunks already retrieved for this session.
3. Chunk-ID heuristics provide a readable fallback when lookup misses.
"""

from __future__ import annotations

import re
from pathlib import Path

from src.vector_store import get_uploaded_collection, get_corpus_collection

_SECTION_RE = re.compile(
    r"(Article\s+\d+(?:\(\d+\))?|Annex\s+[IVXLC]+(?:\(\d+\))?|Chapter\s+[IVXLC]+|Recital\s+\d+)",
    re.IGNORECASE,
)
_CORPUS_CHUNK_RE = re.compile(r"^corpus_(?P<stem>.+?)_chunk(?P<index>\d+)$", re.IGNORECASE)
_UPLOADED_CHUNK_RE = re.compile(
    r"^(?P<prefix>(?:sess_[^_]+_)?(?P<doc>.+?))_chunk(?P<index>\d+)$",
    re.IGNORECASE,
)

_EVIDENCE_TYPE_LABELS = {
    "uploaded_document": "Uploaded document",
    "regulation": "Regulation",
    "official_guidance": "Official guidance",
    "unknown": "Unknown",
}

_CORPUS_TITLE_BY_STEM = {
    "eu_ai_act": "EU AI Act (Regulation 2024/1689)",
    "guidelines_on_prohibited_artificial_intelligence_practices_under_the_ai_act": (
        "Commission Guidelines on Prohibited AI Practices"
    ),
    "commission_guidelines_on_the_definition_of_an_ai_system": (
        "Commission Guidelines on the Definition of an AI System"
    ),
}


def resolve_citations(
    chunk_ids: list[str],
    *,
    session_id: str = "",
    evidence_cache: list[dict] | None = None,
) -> dict[str, dict]:
    """Resolve chunk IDs to display-ready citation dicts."""
    unique_ids = list(dict.fromkeys(cid.strip() for cid in chunk_ids if cid and cid.strip()))
    if not unique_ids:
        return {}

    cache_index = _index_evidence_cache(evidence_cache or [])
    chroma_hits = _resolve_from_chroma(unique_ids, session_id=session_id)

    lookup: dict[str, dict] = {}
    for cid in unique_ids:
        if cid in chroma_hits:
            lookup[cid] = _normalize_entry(chroma_hits[cid], resolver="chroma")
        elif cid in cache_index:
            lookup[cid] = _normalize_entry(cache_index[cid], resolver="evidence_cache")
        else:
            lookup[cid] = _normalize_entry(_resolve_from_chunk_id(cid), resolver="chunk_id_heuristic")
    return lookup


def resolve_citation(
    chunk_id: str,
    *,
    session_id: str = "",
    evidence_cache: list[dict] | None = None,
) -> dict:
    """Resolve a single chunk_id."""
    return resolve_citations(
        [chunk_id],
        session_id=session_id,
        evidence_cache=evidence_cache,
    ).get(chunk_id, _normalize_entry(_resolve_from_chunk_id(chunk_id), resolver="chunk_id_heuristic"))


def format_source_label(resolved: dict) -> str:
    """Build a single human-readable source string, e.g. 'EU AI Act, Annex III'."""
    label = (resolved.get("source_label") or "").strip()
    section = (resolved.get("section") or "").strip()
    page = resolved.get("page")

    if not label:
        label = resolved.get("chunk_id", "Unknown source")

    parts = [label]
    if section and section.lower() not in label.lower():
        parts.append(section)
    if page:
        parts.append(f"p. {page}")
    return ", ".join(parts)


def evidence_type_label(source_type: str) -> str:
    return _EVIDENCE_TYPE_LABELS.get(source_type or "unknown", "Unknown")


def _resolve_from_chroma(chunk_ids: list[str], session_id: str = "") -> dict[str, dict]:
    hits: dict[str, dict] = {}
    remaining = list(chunk_ids)

    uploaded = get_uploaded_collection()
    if uploaded.count() > 0 and remaining:
        try:
            results = uploaded.get(ids=remaining, include=["documents", "metadatas"])
            for cid, text, meta in zip(
                results.get("ids", []),
                results.get("documents", []),
                results.get("metadatas", []),
            ):
                if session_id and meta and meta.get("session_id") not in ("", session_id):
                    continue
                hits[cid] = _entry_from_store(cid, text or "", meta or {}, fallback_type="uploaded_document")
            remaining = [cid for cid in remaining if cid not in hits]
        except Exception:
            pass

    if remaining:
        corpus = get_corpus_collection()
        if corpus.count() > 0:
            try:
                results = corpus.get(ids=remaining, include=["documents", "metadatas"])
                for cid, text, meta in zip(
                    results.get("ids", []),
                    results.get("documents", []),
                    results.get("metadatas", []),
                ):
                    hits[cid] = _entry_from_store(cid, text or "", meta or {}, fallback_type="regulation")
            except Exception:
                pass

    return hits


def _entry_from_store(chunk_id: str, text: str, meta: dict, fallback_type: str) -> dict:
    source_type = meta.get("source_type") or fallback_type
    filename = meta.get("filename", "")
    title = meta.get("title", "")
    section = (meta.get("section") or "").strip() or _infer_section_from_text(text)

    if source_type in ("regulation", "official_guidance"):
        source_label = title or _title_from_corpus_stem(_parse_corpus_stem(chunk_id)) or "EU AI Act"
    else:
        source_label = _prettify_doc_name(filename) or _title_from_uploaded_id(chunk_id) or chunk_id

    return {
        "chunk_id": chunk_id,
        "found": True,
        "source_type": source_type,
        "source_label": source_label,
        "section": section,
        "page": meta.get("page") or None,
        "excerpt": _make_excerpt(text, section=section),
        "filename": filename,
        "text": text,
    }


def _index_evidence_cache(chunks: list[dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for chunk in chunks:
        cid = chunk.get("chunk_id")
        if not cid:
            continue
        section = (chunk.get("section") or _infer_section_from_text(chunk.get("text", ""))).strip()
        index[cid] = {
            "chunk_id": cid,
            "found": True,
            "source_type": chunk.get("source_type") or _guess_source_type_from_id(cid),
            "source_label": (
                chunk.get("title")
                or _prettify_doc_name(chunk.get("filename", ""))
                or _title_from_uploaded_id(cid)
                or _title_from_corpus_stem(_parse_corpus_stem(cid))
                or cid
            ),
            "section": section,
            "page": chunk.get("page") or None,
            "excerpt": _make_excerpt(chunk.get("text", ""), section=section),
            "filename": chunk.get("filename", ""),
            "text": chunk.get("text", ""),
        }
    return index


def _resolve_from_chunk_id(chunk_id: str) -> dict:
    source_type = _guess_source_type_from_id(chunk_id)

    if source_type in ("regulation", "official_guidance"):
        stem = _parse_corpus_stem(chunk_id)
        return {
            "chunk_id": chunk_id,
            "found": False,
            "source_type": source_type,
            "source_label": _title_from_corpus_stem(stem),
            "section": _section_from_corpus_id(chunk_id),
            "page": None,
            "excerpt": "",
            "filename": f"{stem}.html" if stem else "",
            "text": "",
        }

    return {
        "chunk_id": chunk_id,
        "found": False,
        "source_type": "uploaded_document",
        "source_label": _title_from_uploaded_id(chunk_id),
        "section": "",
        "page": None,
        "excerpt": "",
        "filename": _filename_from_uploaded_id(chunk_id),
        "text": "",
    }


def _parse_corpus_stem(chunk_id: str) -> str:
    match = _CORPUS_CHUNK_RE.match(chunk_id)
    return match.group("stem") if match else ""


def _section_from_corpus_id(chunk_id: str) -> str:
    stem = _parse_corpus_stem(chunk_id)
    if not stem:
        return ""
    article = re.search(r"article[_\s-]?(\d+)", stem, re.IGNORECASE)
    if article:
        return f"Article {article.group(1)}"
    annex = re.search(r"annex[_\s-]?([ivxlc]+)", stem, re.IGNORECASE)
    if annex:
        return f"Annex {annex.group(1).upper()}"
    return ""


def _title_from_corpus_stem(stem: str) -> str:
    if not stem:
        return "EU AI Act (Regulation 2024/1689)"
    key = stem.lower()
    if key in _CORPUS_TITLE_BY_STEM:
        return _CORPUS_TITLE_BY_STEM[key]
    if "prohibited" in key:
        return "Commission Guidelines on Prohibited AI Practices"
    if "definition" in key and "system" in key:
        return "Commission Guidelines on the Definition of an AI System"
    if "ai_act" in key or "1689" in key:
        return "EU AI Act (Regulation 2024/1689)"
    return stem.replace("_", " ").strip()


def _title_from_uploaded_id(chunk_id: str) -> str:
    match = _UPLOADED_CHUNK_RE.match(chunk_id)
    if not match:
        return _prettify_doc_name(chunk_id)
    doc = match.group("doc")
    return _prettify_doc_name(doc.replace("-", "_") + ".pdf") or doc.replace("-", " ").title()


def _filename_from_uploaded_id(chunk_id: str) -> str:
    match = _UPLOADED_CHUNK_RE.match(chunk_id)
    if not match:
        return ""
    return f"{match.group('doc')}.pdf"


def _guess_source_type_from_id(chunk_id: str) -> str:
    lower = chunk_id.lower()
    if lower.startswith("corpus"):
        stem = _parse_corpus_stem(chunk_id).lower()
        if "guideline" in stem or "guidance" in stem:
            return "official_guidance"
        return "regulation"
    return "uploaded_document"


def _normalize_entry(raw: dict, resolver: str) -> dict:
    entry = {
        "chunk_id": raw.get("chunk_id", ""),
        "found": bool(raw.get("found", False)),
        "source_type": raw.get("source_type") or "unknown",
        "source_label": (raw.get("source_label") or raw.get("chunk_id") or "").strip(),
        "section": (raw.get("section") or "").strip(),
        "page": raw.get("page"),
        "excerpt": (raw.get("excerpt") or _make_excerpt(raw.get("text", ""), section=(raw.get("section") or "").strip())).strip(),
        "filename": raw.get("filename", ""),
        "source": "",
        "evidence_type": evidence_type_label(raw.get("source_type") or "unknown"),
        "resolver": resolver,
    }
    entry["source"] = format_source_label(entry)
    return entry


def _infer_section_from_text(text: str) -> str:
    match = _SECTION_RE.search(text or "")
    if not match:
        return ""
    section = match.group(1).strip()
    if section.lower().startswith("annex"):
        return section.replace("annex", "Annex").replace("ANNEX", "Annex")
    if section.lower().startswith("article"):
        return section.title().replace("Article", "Article")
    return section


def _prettify_doc_name(name: str) -> str:
    if not name:
        return ""
    stem = Path(name).stem if "." in name else name
    stem = re.sub(r"^(sess_[^_]+_)", "", stem, flags=re.IGNORECASE)
    stem = stem.replace("-", " ").replace("_", " ")
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem.title() if stem else ""


_SUBSTANTIVE_KEYWORDS = (
    "shall", "prohibited", "high-risk", "high risk", "unacceptable",
    "employment", "worker", "recruit", "candidate", "ai system",
    "deployer", "provider", "obligation", "transparency", "risk",
    "annex", "article", "exception", "exceptional",
)


def _clean_chunk_text(text: str) -> str:
    text = text or ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^\s*\|[-:\s|]+\|\s*$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"\|[-:\s|]+\|", " ", text)
    text = re.sub(r"\|+", " ", text)
    text = re.sub(r"\s*\|\s*", " ", text)
    text = re.sub(r"\(\d+\)\s*\|", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _split_sentences(text: str) -> list[str]:
    cleaned = _clean_chunk_text(text)
    if not cleaned:
        return []

    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    sentences: list[str] = []
    for part in parts:
        s = part.strip(" ,;|")
        s = re.sub(r"^\([a-z0-9]+\)\s*\|?\s*", "", s, flags=re.IGNORECASE)
        if len(s) >= 35:
            sentences.append(s)
    if not sentences and cleaned:
        sentences = [cleaned]
    return sentences


def _score_sentence(sentence: str, section: str = "") -> int:
    score = 0
    lower = sentence.lower()

    if re.search(r"^\(?\d+\)?$", sentence.strip()):
        score -= 10
    if re.match(r"^(regulation|article \d|annex|chapter|recital|\(\d+\))\b", lower):
        score -= 4
    if "|" in sentence or "---" in sentence:
        score -= 8
    if len(sentence) < 45:
        score -= 3
    if not re.search(r"[a-zA-Z]{4,}", sentence):
        score -= 5

    for kw in _SUBSTANTIVE_KEYWORDS:
        if kw in lower:
            score += 2
    if section and section.lower() in lower:
        score += 4
    if sentence[0].isupper():
        score += 1
    else:
        score -= 2
    return score


def _make_excerpt(text: str, max_chars: int = 280, section: str = "") -> str:
    """Pick the most readable sentence from a chunk instead of a blind prefix."""
    sentences = _split_sentences(text)
    if not sentences:
        return ""

    ranked = sorted(
        sentences,
        key=lambda s: (_score_sentence(s, section), len(s)),
        reverse=True,
    )
    best = ranked[0]

    if _score_sentence(best, section) < 1:
        for s in sentences:
            if _score_sentence(s, section) >= 1:
                best = s
                break

    if len(best) <= max_chars:
        return best.rstrip(",;: ") + ("..." if not best.endswith((".", "!", "?")) else "")

    cut = best[:max_chars]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(",;: ") + "..."
