"""
Score and explain how each citation supports its claim.

Purely programmatic — uses assessment context + excerpt/section signals.
Does not call an LLM.
"""

from __future__ import annotations

import re
from typing import Any

from src.citation_resolver import split_sentences

SUPPORT_STRONG = 0.70
SUPPORT_MODERATE = 0.50
SUPPORT_WEAK = 0.30
PRIMARY_MIN_SCORE = 0.50
STRONG_MIN_SCORE = 0.70
SENTENCE_FIT_MIN = 0.15

PRIMARY_RELEVANCE_THRESHOLD = int(PRIMARY_MIN_SCORE * 100)

_UPLOADED_TYPES = {"uploaded_document", "user_input"}
_LEGAL_TYPES = {"regulation", "official_guidance"}

_EVIDENCE_CATEGORY_LABELS = {
    "supported_fact": "Supported fact",
    "regulatory_reference": "Regulatory reference",
    "governance_note": "Governance note",
}

_WEAK_WARNING = (
    "This source is related but does not directly prove the claim."
)

LEGAL_TOPIC_ROUTES: dict[str, dict[str, Any]] = {
    "ai_system_definition": {
        "sections": ["Article 3"],
        "topics": ["ai_system_definition"],
        "law_layers": ["definitions"],
        "keywords": ("ai system", "infer", "learning", "model", "definition"),
    },
    "prohibited_practices": {
        "sections": ["Article 5"],
        "topics": ["prohibited_practices"],
        "law_layers": ["prohibited_practices"],
        "keywords": ("prohibited", "unacceptable", "practice"),
    },
    "employment_recruitment": {
        "sections": ["Annex III"],
        "topics": ["employment_and_worker_management", "recruitment_screening"],
        "law_layers": ["high_risk_annex"],
        "keywords": ("employment", "recruit", "recruitment", "hiring", "worker", "candidate"),
    },
    "safety_component": {
        "sections": ["Article 6"],
        "topics": ["critical_infrastructure", "safety_component", "predictive_maintenance"],
        "law_layers": ["high_risk_annex"],
        "keywords": ("safety component", "critical infrastructure", "machinery"),
    },
    "transparency": {
        "sections": ["Article 50"],
        "topics": ["transparency"],
        "law_layers": ["transparency"],
        "keywords": ("transparency", "disclosure", "inform", "chatbot"),
    },
    "gpai": {
        "sections": ["Chapter V"],
        "topics": ["general_purpose_ai", "gpai"],
        "law_layers": ["gpai"],
        "keywords": ("general-purpose", "general purpose", "gpai", "foundation model", "llm"),
    },
    "human_oversight": {
        "sections": ["Article 14"],
        "topics": ["human_oversight"],
        "law_layers": ["core_rules"],
        "keywords": ("human oversight", "human intervention", "supervision"),
    },
    "data_governance": {
        "sections": ["Article 10"],
        "topics": ["data_governance"],
        "law_layers": ["core_rules"],
        "keywords": ("data governance", "training data", "data quality"),
    },
    "documentation": {
        "sections": ["Article 11"],
        "topics": ["documentation"],
        "law_layers": ["core_rules"],
        "keywords": ("technical documentation", "documentation"),
    },
    "robustness": {
        "sections": ["Article 15"],
        "topics": ["robustness", "accuracy"],
        "law_layers": ["core_rules"],
        "keywords": ("accuracy", "robustness", "cybersecurity"),
    },
    "high_risk_annex": {
        "sections": ["Annex III", "Article 6"],
        "topics": ["high_risk_annex"],
        "law_layers": ["high_risk_annex"],
        "keywords": ("high-risk", "high risk", "annex iii"),
    },
    "risk_classification": {
        "sections": ["Annex III", "Article 6"],
        "topics": [],
        "law_layers": ["high_risk_annex", "core_rules"],
        "keywords": ("risk", "classification", "minimal", "high-risk"),
    },
}

_USE_CASE_TOPICS = {
    "predictive_maintenance": (
        "maintenance", "machinery", "industrial", "sensor", "engine", "equipment", "predictive", "lstm",
    ),
    "hr_screening": (
        "recruit", "recruitment", "hiring", "applicant", "candidate", "employment", "hr", "screening",
    ),
    "gpai_use": (
        "gpai", "llm", "gpt", "foundation model", "general-purpose", "general purpose", "third-party",
    ),
}


def enrich_citation_row(
    row: dict,
    *,
    claim_type: str,
    assessment: dict,
) -> dict:
    """Add claim label, support score, explanation, category, and display tier."""
    pa = assessment.get("preliminary_assessment") or {}
    resolved = row.get("_resolved") or {}

    if claim_type == "uploaded_fact":
        claim_label = _uploaded_fact_label(row.get("claim", ""))
        category = "supported_fact"
    elif claim_type == "governance":
        claim_label = row.get("claim", "Governance observation")[:80]
        category = "governance_note"
    else:
        claim_label = _legal_citation_label(resolved, pa)
        category = "regulatory_reference"

    full_text = (
        row.get("full_text")
        or resolved.get("full_text")
        or resolved.get("text")
        or ""
    )
    claim_text = row.get("claim", claim_label)
    excerpt, sentence_fit = select_claim_excerpt(
        full_text,
        claim_text,
        metadata=resolved,
    )
    if excerpt:
        row = {**row, "excerpt": excerpt}
        if resolved:
            resolved = {**resolved, "excerpt": excerpt}
            row["_resolved"] = resolved

    support_score, source_match_reason, components = _compute_support_score(
        claim_type=claim_type,
        claim_label=claim_label,
        claim_text=claim_text,
        row=row,
        resolved=resolved,
        pa=pa,
        assessment=assessment,
        sentence_fit=sentence_fit,
        excerpt=excerpt,
    )

    support_label = _label_from_score(support_score)
    support_reason = _build_support_reason(
        support_label=support_label,
        source_match_reason=source_match_reason,
        components=components,
    )
    warning = _build_warning(support_label, source_match_reason)
    display_tier = _display_tier_from_label(support_label)

    explanation = _build_relevance_explanation(
        claim_type=claim_type,
        claim_label=claim_label,
        row=row,
        resolved=resolved,
        pa=pa,
        assessment=assessment,
        support_label=support_label,
        support_reason=support_reason,
    )

    enriched = {
        **row,
        "claim": claim_label,
        "claim_label": claim_label,
        "evidence_category": category,
        "evidence_category_label": _EVIDENCE_CATEGORY_LABELS.get(category, category),
        "support_score": round(support_score, 3),
        "support_label": support_label,
        "support_reason": support_reason,
        "source_match_reason": source_match_reason,
        "warning": warning,
        "relevance_score": int(round(support_score * 100)),
        "relevance_explanation": explanation,
        "display_tier": display_tier,
    }
    return enriched


def select_claim_excerpt(
    full_text: str,
    claim: str,
    *,
    metadata: dict | None = None,
    max_chars: int = 280,
) -> tuple[str, float]:
    """Pick 1–3 sentences from full_text with best claim overlap."""
    sentences = split_sentences(full_text)
    if not sentences:
        return "", 0.0

    claim_words = set(_keywords(claim))
    claim_entities = set(_entities(claim))
    if not claim_words and not claim_entities:
        return "", 0.0

    best_score = 0.0
    best_text = ""
    best_idx = 0

    for idx, sentence in enumerate(sentences):
        score = _sentence_overlap_score(sentence, claim_words, claim_entities)
        if score > best_score:
            best_score = score
            best_idx = idx
            best_text = sentence

    if best_score < SENTENCE_FIT_MIN:
        return "", best_score

    selected = [best_text]
    total_len = len(best_text)
    for neighbor_idx in (best_idx - 1, best_idx + 1):
        if 0 <= neighbor_idx < len(sentences) and len(selected) < 3:
            neighbor = sentences[neighbor_idx]
            if total_len + len(neighbor) + 1 <= max_chars:
                if neighbor_idx < best_idx:
                    selected.insert(0, neighbor)
                else:
                    selected.append(neighbor)
                total_len += len(neighbor) + 1

    excerpt = " ".join(selected).strip()
    if len(excerpt) > max_chars:
        cut = excerpt[:max_chars]
        if " " in cut:
            cut = cut[: cut.rfind(" ")]
        excerpt = cut.rstrip(",;: ") + "…"
    elif excerpt and not excerpt.endswith((".", "!", "?")):
        excerpt = excerpt.rstrip(",;: ") + "…"

    section = (metadata or {}).get("section") or (metadata or {}).get("article") or ""
    if section and section.lower() not in excerpt.lower() and len(excerpt) < max_chars - len(section) - 4:
        pass

    return excerpt, best_score


def validate_risk_classification_evidence(
    assessment: dict,
    enriched_rows: list[dict],
) -> dict[str, Any]:
    """Check risk tier has both uploaded facts and matching legal references."""
    pa = assessment.get("preliminary_assessment") or {}
    risk_tier = pa.get("risk_tier", "")
    if not risk_tier or risk_tier == "unclear":
        return {"ok": True, "warnings": []}

    strong_labels = {"strong", "moderate"}
    uploaded_ok = any(
        r.get("evidence_category") == "supported_fact"
        and r.get("support_label") in strong_labels
        for r in enriched_rows
    )
    legal_ok = any(
        r.get("evidence_category") == "regulatory_reference"
        and r.get("support_label") in strong_labels
        for r in enriched_rows
    )

    warnings: list[str] = []
    if not uploaded_ok:
        warnings.append(
            "Risk classification lacks strong uploaded-document evidence about the AI system."
        )
    if not legal_ok:
        warnings.append(
            "Risk classification lacks strong regulatory citations matching the claimed category."
        )
    if risk_tier == "gpai_obligations":
        gpai_fact = (assessment.get("extracted_facts") or {}).get("uses_gpai") or {}
        gpai_value = (gpai_fact.get("value") or "").lower()
        if not any(k in gpai_value for k in _USE_CASE_TOPICS["gpai_use"]):
            warnings.append(
                "GPAI obligations claimed but uploaded facts do not mention GPAI, LLM, or foundation models."
            )

    return {
        "ok": uploaded_ok and legal_ok,
        "uploaded_evidence_ok": uploaded_ok,
        "legal_evidence_ok": legal_ok,
        "warnings": warnings,
    }


def score_citation_for_fact(
    claim: str,
    resolved: dict,
    assessment: dict,
) -> dict[str, Any]:
    """Score a resolved citation card against a fact claim (for fact section cards)."""
    row = {"claim": claim, "_resolved": resolved, "excerpt": resolved.get("excerpt", "")}
    enriched = enrich_citation_row(row, claim_type="uploaded_fact", assessment=assessment)
    return {
        "support_score": enriched.get("support_score"),
        "support_label": enriched.get("support_label"),
        "support_reason": enriched.get("support_reason"),
        "source_match_reason": enriched.get("source_match_reason"),
        "warning": enriched.get("warning"),
        "excerpt": enriched.get("excerpt"),
    }


def build_system_inference(assessment: dict) -> dict:
    """Separate system conclusions from direct quotes."""
    pa = assessment.get("preliminary_assessment") or {}
    risk = pa.get("risk_tier", "unclear")
    risk_phrase = {
        "minimal_risk": "minimal risk",
        "high_risk_candidate": "high-risk (Annex III candidate)",
        "prohibited": "prohibited practice",
        "limited_risk": "limited risk (transparency obligations)",
        "gpai_obligations": "GPAI-related obligations",
        "unclear": "unclear classification",
    }.get(risk, risk.replace("_", " "))

    ai_reasoning = (pa.get("ai_system_reasoning") or "").strip()
    risk_reasoning = (pa.get("reasoning") or "").strip()
    confidence = pa.get("confidence", "low")

    parts = []
    if ai_reasoning:
        parts.append(ai_reasoning)
    if risk_reasoning:
        parts.append(risk_reasoning)

    summary = " ".join(parts).strip()
    if not summary:
        summary = (
            f"The system inferred a preliminary classification of {risk_phrase} "
            f"(confidence: {confidence}), based on uploaded facts and regulatory references below."
        )

    return {
        "title": "System inference (not a direct quote)",
        "ai_system_reasoning": ai_reasoning,
        "risk_reasoning": risk_reasoning,
        "summary": summary,
        "risk_tier": risk,
        "confidence": confidence,
        "note": (
            "Risk tiers such as 'minimal risk' are often conclusions inferred by the "
            "assessment agent — not sentences copied verbatim from the AI Act or uploads."
        ),
    }


# ---------------------------------------------------------------------------
# Claim labels
# ---------------------------------------------------------------------------

def _uploaded_fact_label(claim: str) -> str:
    if ":" in claim:
        label, value = claim.split(":", 1)
        return f"Uploaded fact: {label.strip().lower()} — {value.strip()}"
    return f"Uploaded fact: {claim}"


def _legal_citation_label(resolved: dict, pa: dict) -> str:
    section = (resolved.get("section") or "").lower()
    excerpt = (resolved.get("excerpt") or "").lower()
    source = (resolved.get("source_label") or "").lower()
    topic = (resolved.get("topic") or "").lower()
    risk = pa.get("risk_tier", "")

    if "article 3" in section or topic == "ai_system_definition":
        return "AI system definition"
    if "article 5" in section or "prohibited" in source or "prohibited" in excerpt:
        return "Prohibited-practice check"
    if topic in ("employment_and_worker_management", "recruitment_screening"):
        return "Employment / HR high-risk area check"
    if "annex iii" in section or "annex iii" in excerpt:
        return "High-risk / Annex III check"
    if "article 6" in section or ("high-risk" in excerpt and "annex" in excerpt):
        return "High-risk / Annex III check"
    if "article 50" in section or "transparency" in excerpt:
        return "Transparency obligations check"
    if "gpai" in excerpt or "general-purpose" in excerpt or topic in ("gpai", "general_purpose_ai"):
        return "GPAI obligations check"
    if "safety component" in excerpt or "safety components" in excerpt:
        return "Safety-component uncertainty"
    if "employment" in excerpt or "recruit" in excerpt or "worker" in excerpt:
        return "Employment / HR high-risk area check"

    if risk in ("minimal_risk", "unclear"):
        return "Risk classification context (regulatory reference)"
    if risk == "high_risk_candidate":
        return "High-risk classification support"
    if risk == "prohibited":
        return "Prohibited-practice support"
    return "Regulatory reference"


def _infer_claim_topic(
    claim_type: str,
    claim_label: str,
    assessment: dict,
) -> str:
    label_lower = claim_label.lower()
    use_context = _detect_use_case_context(assessment)

    if claim_type == "uploaded_fact":
        if "gpai" in label_lower or "uses gpai" in label_lower:
            return "gpai"
        return use_context or "general"

    topic_map = (
        ("ai system definition", "ai_system_definition"),
        ("prohibited", "prohibited_practices"),
        ("employment", "employment_recruitment"),
        ("hr high-risk", "employment_recruitment"),
        ("annex iii", "high_risk_annex"),
        ("high-risk", "high_risk_annex"),
        ("transparency", "transparency"),
        ("gpai", "gpai"),
        ("safety-component", "safety_component"),
        ("risk classification", "risk_classification"),
    )
    for needle, topic_key in topic_map:
        if needle in label_lower:
            if topic_key == "employment_recruitment" and use_context == "predictive_maintenance":
                return "risk_classification"
            if topic_key == "high_risk_annex" and use_context == "predictive_maintenance":
                return "risk_classification"
            return topic_key

    if use_context == "hr_screening":
        return "employment_recruitment"
    if use_context == "predictive_maintenance":
        return "risk_classification"
    return "risk_classification"


def _detect_use_case_context(assessment: dict) -> str:
    use_summary = (assessment.get("use_case_summary") or "").lower()
    facts = assessment.get("extracted_facts") or {}
    sector = (facts.get("sector") or {}).get("value", "").lower()
    purpose = (facts.get("purpose") or {}).get("value", "").lower()
    blob = f"{use_summary} {sector} {purpose}"

    if any(k in blob for k in _USE_CASE_TOPICS["hr_screening"]):
        return "hr_screening"
    if any(k in blob for k in _USE_CASE_TOPICS["predictive_maintenance"]):
        return "predictive_maintenance"
    if any(k in blob for k in _USE_CASE_TOPICS["gpai_use"]):
        return "gpai_use"
    return "general"


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _compute_support_score(
    *,
    claim_type: str,
    claim_label: str,
    claim_text: str,
    row: dict,
    resolved: dict,
    pa: dict,
    assessment: dict,
    sentence_fit: float,
    excerpt: str,
) -> tuple[float, str, dict[str, float]]:
    source_ok, source_match_reason = _check_source_type_match(claim_type, resolved)

    full_text = (
        excerpt
        + " "
        + (row.get("full_text") or resolved.get("full_text") or resolved.get("text") or "")
    ).strip()
    claim_blob = f"{claim_label} {claim_text}"

    keyword_score = _keyword_overlap_score(claim_blob, full_text)
    entity_score = _entity_overlap_score(claim_blob, full_text)
    source_score = 1.0 if source_ok else 0.0

    claim_topic = _infer_claim_topic(claim_type, claim_label, assessment)
    topic_score = _score_topic_match(claim_topic, resolved, assessment, excerpt)

    components = {
        "keyword": keyword_score,
        "entity": entity_score,
        "source_type": source_score,
        "topic": topic_score,
        "sentence_fit": sentence_fit,
    }

    if not source_ok:
        return 0.25, source_match_reason, components

    if not excerpt and sentence_fit < SENTENCE_FIT_MIN:
        return 0.20, "No excerpt sentence overlaps enough with the claim.", components

    weighted = (
        0.25 * keyword_score
        + 0.15 * entity_score
        + 0.25 * source_score
        + 0.20 * topic_score
        + 0.15 * min(1.0, sentence_fit * 3.0)
    )

    if claim_type == "uploaded_fact":
        weighted = max(weighted, 0.35 * keyword_score + 0.40 * sentence_fit)
    elif claim_type == "legal":
        weighted = max(weighted, 0.30 * topic_score + 0.25 * keyword_score)

    if claim_type == "governance":
        obs = row.get("claim", "").lower()
        overlap = sum(1 for w in _keywords(obs) if w in full_text.lower())
        weighted = max(weighted, min(0.85, 0.40 + overlap * 0.08))

    weighted = max(0.0, min(1.0, weighted))

    if topic_score == 0.0 and claim_type == "legal":
        weighted = min(weighted, 0.45)
        source_match_reason = (
            source_match_reason
            + " Legal topic does not match the use-case context."
        ).strip()

    use_context = _detect_use_case_context(assessment)
    chunk_topic = (resolved.get("topic") or "").lower()
    if (
        use_context == "predictive_maintenance"
        and chunk_topic in ("employment_and_worker_management", "recruitment_screening")
        and claim_type == "legal"
    ):
        weighted = min(weighted, 0.35)

    if use_context == "predictive_maintenance" and "employment" in excerpt.lower() and claim_type == "legal":
        weighted = min(weighted, 0.35)

    if use_context == "hr_screening" and claim_type == "legal" and "employment" in excerpt.lower():
        weighted = max(weighted, 0.55)

    risk = pa.get("risk_tier", "")
    if risk in ("minimal_risk", "unclear") and claim_type == "legal":
        if "shall always be considered high-risk" in full_text.lower():
            weighted = min(weighted, 0.55)

    gpai_fact = (assessment.get("extracted_facts") or {}).get("uses_gpai") or {}
    gpai_value = (gpai_fact.get("value") or "").lower()
    if claim_topic == "gpai" and not any(k in gpai_value for k in _USE_CASE_TOPICS["gpai_use"]):
        if "lstm" in gpai_value or "custom" in gpai_value:
            weighted = min(weighted, 0.35)

    if not source_match_reason:
        source_match_reason = "Source type matches claim requirements."

    return round(weighted, 4), source_match_reason, components


def _check_source_type_match(claim_type: str, resolved: dict) -> tuple[bool, str]:
    evidence_type = (resolved.get("evidence_type") or "").lower()
    source_type = (resolved.get("source_type") or "").lower()
    cid = (resolved.get("chunk_id") or "").lower()

    is_uploaded = (
        evidence_type in _UPLOADED_TYPES
        or source_type in _UPLOADED_TYPES
        or (cid and not cid.startswith("corpus"))
    )
    is_legal = (
        evidence_type in _LEGAL_TYPES
        or source_type in _LEGAL_TYPES
        or cid.startswith("corpus")
    )

    if claim_type == "uploaded_fact":
        if is_legal and not is_uploaded:
            return False, "Corpus/regulatory citation cannot support an uploaded-system fact claim."
        return True, "Uploaded or user-input source matches fact claim."

    if claim_type == "legal":
        if is_uploaded and not is_legal:
            return False, "Uploaded document alone cannot support a legal rule claim."
        return True, "Regulatory or guidance source matches legal claim."

    if claim_type == "governance":
        return True, "Governance citations may use uploaded or regulatory sources."

    return True, "Source type acceptable."


def _score_topic_match(
    claim_topic: str,
    resolved: dict,
    assessment: dict,
    excerpt: str,
) -> float:
    route = LEGAL_TOPIC_ROUTES.get(claim_topic)
    if not route:
        return 0.5

    section = (resolved.get("section") or resolved.get("article") or "").lower()
    topic = (resolved.get("topic") or "").lower()
    law_layer = (resolved.get("law_layer") or "").lower()
    text_blob = f"{excerpt} {resolved.get('full_text', '')}".lower()

    score = 0.0
    hits = 0
    checks = 0

    for sec in route.get("sections") or []:
        checks += 1
        if sec.lower() in section or sec.lower() in text_blob:
            hits += 1

    for t in route.get("topics") or []:
        checks += 1
        if t.lower() == topic or t.replace("_", " ") in text_blob:
            hits += 1

    for layer in route.get("law_layers") or []:
        checks += 1
        if layer.lower() == law_layer:
            hits += 1

    for kw in route.get("keywords") or ():
        if kw in text_blob:
            hits += 1
            checks += 1
            break

    if checks == 0:
        return 0.5
    score = hits / checks

    use_context = _detect_use_case_context(assessment)
    chunk_topic = topic

    if use_context == "predictive_maintenance" and chunk_topic in (
        "employment_and_worker_management",
        "recruitment_screening",
    ):
        return 0.0

    if use_context == "hr_screening" and claim_topic == "employment_recruitment":
        if chunk_topic in ("employment_and_worker_management", "recruitment_screening") or "employment" in text_blob:
            return max(score, 0.85)

    if claim_topic == "risk_classification" and use_context == "predictive_maintenance":
        if chunk_topic in ("employment_and_worker_management", "recruitment_screening"):
            return 0.0
        if "employment" in text_blob or "recruit" in text_blob:
            return 0.1

    return min(1.0, score)


def _keyword_overlap_score(claim: str, text: str) -> float:
    claim_words = set(_keywords(claim))
    if not claim_words:
        return 0.3
    text_lower = text.lower()
    matches = sum(1 for w in claim_words if w in text_lower)
    return matches / len(claim_words)


def _entity_overlap_score(claim: str, text: str) -> float:
    entities = set(_entities(claim))
    if not entities:
        return 0.3
    text_lower = text.lower()
    matches = sum(1 for e in entities if e in text_lower)
    return matches / len(entities)


def _sentence_overlap_score(
    sentence: str,
    claim_words: set[str],
    claim_entities: set[str],
) -> float:
    lower = sentence.lower()
    if not claim_words and not claim_entities:
        return 0.0
    word_hits = sum(1 for w in claim_words if w in lower)
    entity_hits = sum(1 for e in claim_entities if e in lower)
    word_ratio = word_hits / max(len(claim_words), 1)
    entity_ratio = entity_hits / max(len(claim_entities), 1) if claim_entities else word_ratio
    return 0.6 * word_ratio + 0.4 * entity_ratio


def _label_from_score(score: float) -> str:
    if score >= SUPPORT_STRONG:
        return "strong"
    if score >= SUPPORT_MODERATE:
        return "moderate"
    if score >= SUPPORT_WEAK:
        return "weak"
    return "unsupported"


def _display_tier_from_label(support_label: str) -> str:
    if support_label in ("strong", "moderate"):
        return "primary"
    if support_label == "weak":
        return "additional"
    return "unsupported"


def _build_support_reason(
    *,
    support_label: str,
    source_match_reason: str,
    components: dict[str, float],
) -> str:
    parts = [f"Support tier: {support_label}."]
    if source_match_reason:
        parts.append(source_match_reason)
    low = [k for k, v in components.items() if v < 0.35]
    if low:
        parts.append(f"Weak signals: {', '.join(low)}.")
    return " ".join(parts)


def _build_warning(support_label: str, source_match_reason: str) -> str | None:
    if support_label in ("weak", "unsupported"):
        return _WEAK_WARNING
    if support_label == "moderate":
        return None
    if "cannot support" in (source_match_reason or "").lower():
        return _WEAK_WARNING
    return None


def _keywords(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z]{4,}", (text or "").lower())
    stop = {
        "that", "this", "with", "from", "have", "been", "were", "their", "which",
        "about", "unclear", "uploaded", "fact", "regulatory", "reference", "claim",
    }
    return [w for w in words if w not in stop][:16]


def _entities(text: str) -> list[str]:
    lower = (text or "").lower()
    found: list[str] = []
    patterns = (
        r"article\s+\d+(?:\(\d+\))?",
        r"annex\s+[ivxlc]+(?:\(\d+\))?",
        r"\blstm\b",
        r"\bgpai\b",
        r"\bllm\b",
        r"predictive\s+maintenance",
        r"safety\s+component",
        r"high-risk",
        r"recruit(?:ment)?",
        r"employment",
    )
    for pat in patterns:
        for m in re.finditer(pat, lower):
            found.append(m.group(0).strip())
    found.extend(_keywords(lower)[:6])
    return list(dict.fromkeys(found))[:12]


# ---------------------------------------------------------------------------
# Relevance explanations
# ---------------------------------------------------------------------------

def _build_relevance_explanation(
    *,
    claim_type: str,
    claim_label: str,
    row: dict,
    resolved: dict,
    pa: dict,
    assessment: dict,
    support_label: str,
    support_reason: str,
) -> str:
    risk = pa.get("risk_tier", "")
    use_summary = (assessment.get("use_case_summary") or "").strip()
    context_snippet = use_summary[:120] + ("…" if len(use_summary) > 120 else "") if use_summary else "this use case"

    if support_label in ("weak", "unsupported"):
        return (
            f"{support_reason} "
            "This source is related but does not directly prove the claim."
        )

    if claim_type == "uploaded_fact":
        if ":" in row.get("claim", ""):
            _, value = row["claim"].split(":", 1)
            return (
                f"The uploaded document supports the fact “{value.strip()}” "
                f"({support_label} support). "
                f"The cited excerpt describes this from user-provided material."
            )
        return (
            f"This excerpt comes from an uploaded document cited as factual evidence "
            f"({support_label} support)."
        )

    if claim_type == "governance":
        return (
            f"This source was cited for a governance observation ({support_label} support). "
            "Review whether the excerpt matches the specific compliance area."
        )

    label_lower = claim_label.lower()

    if "ai system definition" in label_lower:
        return (
            f"This excerpt sets out AI system criteria under the EU AI Act ({support_label} support). "
            f"The assessment compared those criteria to {context_snippet}."
        )

    if "prohibited" in label_lower:
        return (
            f"This regulatory excerpt describes prohibited AI practices ({support_label} support). "
            "The assessment checked whether the use case falls within any prohibition."
        )

    if "annex iii" in label_lower or "high-risk" in label_lower:
        if support_label == "moderate" or risk in ("minimal_risk", "unclear"):
            return (
                f"This Annex III / high-risk excerpt provides comparison context ({support_label} support). "
                f"It does not by itself prove high-risk for {context_snippet}."
            )
        return (
            f"This excerpt lists high-risk conditions ({support_label} support). "
            "The assessment linked it to uploaded facts suggesting Annex III relevance."
        )

    if support_label == "moderate":
        return (
            f"This regulatory excerpt provides partial context ({support_label} support). "
            "The final risk tier is still a system inference."
        )

    return (
        f"This regulatory excerpt provides legal context ({support_label} support). "
        "The final risk tier is still a system inference — see ‘System inference’ above."
    )
