"""
Validate and repair Assessment Agent citation assignments.

Runs programmatically after the LLM returns JSON — before Critic / Presenter.
Strips citations that violate source-type rules, are absent from the evidence
pack, or score as unsupported for their claim context.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from src.citation_relevance import (
    _detect_use_case_context,
    enrich_citation_row,
)
from src.citation_resolver import resolve_citation

_MOCK_UPLOADED_RE = re.compile(r"^uploaded:chunk(?P<index>\d+)$", re.IGNORECASE)
_CORPUS_PREFIXES = ("corpus", "corpus:")


def build_evidence_index(
    uploaded_chunks: list[dict],
    corpus_chunks: list[dict],
    extra_chunks: list[dict] | None = None,
) -> dict[str, dict]:
    """Map chunk_id -> chunk dict for all evidence shown to the Assessment Agent."""
    index: dict[str, dict] = {}
    for chunk in (uploaded_chunks or []) + (corpus_chunks or []) + (extra_chunks or []):
        cid = (chunk.get("chunk_id") or "").strip()
        if cid:
            index[cid] = chunk
    return index


def validate_and_repair_assessment(
    assessment: dict,
    *,
    uploaded_chunks: list[dict],
    corpus_chunks: list[dict],
    extra_chunks: list[dict] | None = None,
    strict_pack: bool = True,
) -> dict:
    """
    Return a copy of assessment with invalid citations removed and confidence adjusted.

    Adds assessment["_meta"]["citation_repairs"] listing each repair action.
    """
    out = copy.deepcopy(assessment)
    index = build_evidence_index(uploaded_chunks, corpus_chunks, extra_chunks)
    repairs: list[dict] = []

    uploaded_ids = [
        cid for cid, c in index.items()
        if _chunk_is_uploaded(c, cid)
    ]
    corpus_ids = [
        cid for cid, c in index.items()
        if _chunk_is_corpus(c, cid)
    ]

    # --- extracted facts ---
    facts = out.get("extracted_facts") or {}
    for key, fact in facts.items():
        if not isinstance(fact, dict):
            continue
        label = key.replace("_", " ").title()
        value = (fact.get("value") or "").strip()
        claim_text = f"{label}: {value}"
        kept: list[str] = []
        for raw_cid in fact.get("evidence") or []:
            cid, reason = _normalize_and_validate_id(
                raw_cid,
                index=index,
                uploaded_ids=uploaded_ids,
                corpus_ids=corpus_ids,
                claim_type="uploaded_fact",
                assessment=out,
                strict_pack=strict_pack,
                claim_text=claim_text,
            )
            if cid:
                kept.append(cid)
            elif reason:
                repairs.append({"field": f"extracted_facts.{key}", "chunk_id": raw_cid, "action": reason})
        fact["evidence"] = kept
        if fact.get("confidence") == "high" and not kept:
            fact["confidence"] = "medium"
            repairs.append({
                "field": f"extracted_facts.{key}",
                "action": "lowered_confidence",
                "detail": "high -> medium after removing invalid evidence",
            })

    # --- legal citations ---
    pa = out.setdefault("preliminary_assessment", {})
    legal_kept: list[str] = []
    for raw_cid in pa.get("legal_citations") or []:
        cid, reason = _normalize_and_validate_id(
            raw_cid,
            index=index,
            uploaded_ids=uploaded_ids,
            corpus_ids=corpus_ids,
            claim_type="legal",
            assessment=out,
            strict_pack=strict_pack,
            claim_text=(pa.get("reasoning") or "")[:200],
        )
        if cid:
            legal_kept.append(cid)
        elif reason:
            repairs.append({"field": "preliminary_assessment.legal_citations", "chunk_id": raw_cid, "action": reason})
    pa["legal_citations"] = legal_kept
    if pa.get("confidence") == "high" and not legal_kept and pa.get("risk_tier") not in ("unclear",):
        pa["confidence"] = "medium"
        repairs.append({
            "field": "preliminary_assessment",
            "action": "lowered_confidence",
            "detail": "legal citations removed or empty",
        })

    # --- governance ---
    for i, obs in enumerate(out.get("governance_observations") or []):
        if not isinstance(obs, dict):
            continue
        gov_kept: list[str] = []
        claim = (obs.get("observation") or "")[:120]
        for raw_cid in obs.get("citations") or []:
            cid, reason = _normalize_and_validate_id(
                raw_cid,
                index=index,
                uploaded_ids=uploaded_ids,
                corpus_ids=corpus_ids,
                claim_type="governance",
                assessment=out,
                strict_pack=strict_pack,
                claim_text=claim,
            )
            if cid:
                gov_kept.append(cid)
            elif reason:
                repairs.append({
                    "field": f"governance_observations[{i}]",
                    "chunk_id": raw_cid,
                    "action": reason,
                })
        obs["citations"] = gov_kept

    if repairs:
        missing = out.setdefault("missing_information", [])
        if not any(m.get("topic") == "Citation support" for m in missing if isinstance(m, dict)):
            missing.append({
                "topic": "Citation support",
                "why_it_matters": "Some citations were removed because they did not directly support their claims.",
                "suggested_question": "Can you provide documentation that directly supports the flagged claims?",
            })

    meta = out.setdefault("_meta", {})
    if repairs:
        meta["citation_repairs"] = repairs
    meta["citation_validation"] = {
        "uploaded_ids_in_pack": len(uploaded_ids),
        "corpus_ids_in_pack": len(corpus_ids),
        "repairs_count": len(repairs),
    }
    return out


def _normalize_and_validate_id(
    raw_cid: str,
    *,
    index: dict[str, dict],
    uploaded_ids: list[str],
    corpus_ids: list[str],
    claim_type: str,
    assessment: dict,
    strict_pack: bool,
    claim_text: str = "",
) -> tuple[str | None, str | None]:
    """Return (normalized_id, removal_reason). normalized_id None if citation rejected."""
    cid = (raw_cid or "").strip()
    if not cid:
        return None, "empty_chunk_id"

    resolved_id = _resolve_to_pack_id(cid, index, uploaded_ids, corpus_ids, strict_pack=strict_pack)
    if resolved_id is None:
        return None, "not_in_evidence_pack"

    chunk = index.get(resolved_id) or {}
    if claim_type == "uploaded_fact" and not _chunk_is_uploaded(chunk, resolved_id):
        return None, "corpus_cannot_support_uploaded_fact"

    if claim_type == "legal" and not _chunk_is_corpus(chunk, resolved_id):
        return None, "uploaded_cannot_support_legal_claim"

    if claim_type == "legal" and _legal_topic_mismatch(resolved_id, chunk, assessment):
        return None, "legal_topic_mismatch_for_use_case"

    if strict_pack and not _passes_support_threshold(
        resolved_id, chunk, claim_type, assessment, claim_text=claim_text, index=index
    ):
        return None, "weak_or_unsupported_for_claim"

    return resolved_id, None


def _resolve_to_pack_id(
    cid: str,
    index: dict[str, dict],
    uploaded_ids: list[str],
    corpus_ids: list[str],
    *,
    strict_pack: bool,
) -> str | None:
    if cid in index:
        return cid

    mock_match = _MOCK_UPLOADED_RE.match(cid)
    if mock_match:
        idx = int(mock_match.group("index"))
        if idx < len(uploaded_ids):
            return uploaded_ids[idx]

    if cid not in index and _looks_like_corpus_id(cid) and corpus_ids:
        mapped = _map_mock_corpus_id(cid, index, corpus_ids)
        if mapped:
            return mapped

    if not strict_pack and _looks_like_corpus_id(cid):
        return cid if cid in index else None

    return None


def _map_mock_corpus_id(cid: str, index: dict[str, dict], corpus_ids: list[str]) -> str | None:
    """Map fixture-style corpus IDs (corpus:article_6) to a pack corpus chunk when possible."""
    hint = cid.lower().replace(":", "_")
    for pack_id in corpus_ids:
        chunk = index.get(pack_id) or {}
        section = (chunk.get("section") or chunk.get("article") or "").lower()
        topic = (chunk.get("topic") or "").lower()
        text = (chunk.get("text") or "").lower()
        if "annex_iii" in hint or "annex_iii" in hint.replace("area", ""):
            if "annex iii" in section or "annex iii" in text or "employment" in topic:
                return pack_id
        if "article_5" in hint or "prohibited" in hint:
            if "article 5" in section or "prohibited" in topic:
                return pack_id
        if "article_50" in hint or "transparency" in hint:
            if "article 50" in section or "transparency" in topic:
                return pack_id
        if "article_6" in hint:
            if "article 6" in section:
                return pack_id
        if "article_3" in hint:
            if "article 3" in section or topic == "ai_system_definition":
                return pack_id
        if "article_14" in hint:
            if "article 14" in section:
                return pack_id
        if "article_11" in hint:
            if "article 11" in section:
                return pack_id
        if "article_9" in hint:
            if "article 9" in section:
                return pack_id
        if "gpai" in hint or "chapter_v" in hint:
            if topic in ("gpai", "general_purpose_ai") or "gpai" in topic:
                return pack_id
    # Last resort for mock fixtures: first corpus chunk whose section appears in hint
    for pack_id in corpus_ids:
        section = (index.get(pack_id, {}).get("section") or "").lower().replace(" ", "_")
        if section and section.replace("_", "") in hint.replace("_", ""):
            return pack_id
    return None


def _looks_like_corpus_id(cid: str) -> bool:
    lower = cid.lower()
    return lower.startswith(_CORPUS_PREFIXES) or "article" in lower or "annex" in lower


def _chunk_is_uploaded(chunk: dict, cid: str) -> bool:
    st = (chunk.get("source_type") or chunk.get("evidence_type") or "").lower()
    if st in ("uploaded_document", "user_input", "demo_case"):
        return True
    lower = cid.lower()
    return bool(lower) and not lower.startswith("corpus") and "article" not in lower and "annex" not in lower


def _chunk_is_corpus(chunk: dict, cid: str) -> bool:
    st = (chunk.get("source_type") or "").lower()
    if st in ("regulation", "official_guidance"):
        return True
    return _looks_like_corpus_id(cid)


def _legal_topic_mismatch(cid: str, chunk: dict, assessment: dict) -> bool:
    """Reject clearly wrong legal topics for the detected use-case context."""
    context = _detect_use_case_context(assessment)
    topic = (chunk.get("topic") or "").lower()
    text = (chunk.get("text") or "").lower()
    cid_lower = cid.lower()

    if context == "predictive_maintenance":
        employment_signals = (
            topic in ("employment_and_worker_management", "recruitment_screening")
            or any(k in text for k in ("recruitment", "selection of natural persons", "job applicant"))
            or any(k in cid_lower for k in ("employment", "recruit", "annex_iii_area_4"))
        )
        if employment_signals:
            return True

    if context == "gpai_use":
        return False

    facts = assessment.get("extracted_facts") or {}
    gpai_val = (facts.get("uses_gpai") or {}).get("value", "").lower()
    if context != "gpai_use" and "gpai" in topic:
        if not any(k in gpai_val for k in ("gpai", "llm", "gpt", "foundation")):
            return True

    return False


def _passes_support_threshold(
    cid: str,
    chunk: dict,
    claim_type: str,
    assessment: dict,
    *,
    claim_text: str,
    index: dict[str, dict],
) -> bool:
    """Use citation_relevance scoring; require at least weak support when text exists."""
    text = (chunk.get("text") or "").strip()
    if not text and cid not in index:
        resolved = resolve_citation(cid, evidence_cache=list(index.values()))
    else:
        resolved = {
            "chunk_id": cid,
            "found": bool(text),
            "source_type": chunk.get("source_type", ""),
            "evidence_type": chunk.get("evidence_type", ""),
            "topic": chunk.get("topic", ""),
            "law_layer": chunk.get("law_layer", ""),
            "section": chunk.get("section", ""),
            "article": chunk.get("article", ""),
            "full_text": text,
            "text": text,
            "excerpt": "",
        }

    if claim_type == "uploaded_fact":
        claim = claim_text or "Uploaded fact"
    elif claim_type == "legal":
        claim = claim_text or "Regulatory reference"
    else:
        claim = claim_text or "Governance observation"

    row = {"claim": claim, "_resolved": resolved, "excerpt": ""}
    enriched = enrich_citation_row(row, claim_type=claim_type, assessment=assessment)
    label = enriched.get("support_label", "unsupported")
    if claim_type == "legal":
        return label in ("strong", "moderate")
    return label in ("strong", "moderate", "weak")


def _collect_citation_ids(assessment: dict) -> list[str]:
    ids: list[str] = []
    pa = assessment.get("preliminary_assessment") or {}
    ids.extend(pa.get("legal_citations") or [])
    for fact in (assessment.get("extracted_facts") or {}).values():
        if isinstance(fact, dict):
            ids.extend(fact.get("evidence") or [])
    for obs in assessment.get("governance_observations") or []:
        if isinstance(obs, dict):
            ids.extend(obs.get("citations") or [])
    return [c for c in ids if c]


def format_cited_chunks_for_critic(
    assessment: dict,
    evidence_index: dict[str, dict],
    *,
    max_chars: int = 600,
) -> str:
    """Build full-text excerpts for chunk_ids cited in the assessment."""
    ids = _collect_citation_ids(assessment)
    if not ids:
        return "(no citations in assessment)"

    lines: list[str] = []
    for cid in ids:
        chunk = evidence_index.get(cid)
        if not chunk:
            lines.append(f"- {cid} — (not in evidence pack)")
            continue
        text = (chunk.get("text") or "")[:max_chars]
        if len(chunk.get("text") or "") > max_chars:
            text += " […]"
        meta = []
        if chunk.get("topic"):
            meta.append(f"topic={chunk['topic']}")
        if chunk.get("section"):
            meta.append(f"section={chunk['section']}")
        suffix = f" ({', '.join(meta)})" if meta else ""
        lines.append(f"- {cid}{suffix}\n{text}")
    return "\n\n".join(lines)
