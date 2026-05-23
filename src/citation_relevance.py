"""
Score and explain how each citation supports its claim.

Purely programmatic — uses assessment context + excerpt/section signals.
Does not call an LLM.
"""

from __future__ import annotations

import re

PRIMARY_RELEVANCE_THRESHOLD = 55

_EVIDENCE_CATEGORY_LABELS = {
    "supported_fact": "Supported fact",
    "regulatory_reference": "Regulatory reference",
    "governance_note": "Governance note",
}


def enrich_citation_row(
    row: dict,
    *,
    claim_type: str,
    assessment: dict,
) -> dict:
    """Add claim label, relevance score, explanation, category, and display tier."""
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

    score = _score_relevance(
        claim_type=claim_type,
        claim_label=claim_label,
        row=row,
        resolved=resolved,
        pa=pa,
        assessment=assessment,
    )
    explanation = _build_relevance_explanation(
        claim_type=claim_type,
        claim_label=claim_label,
        row=row,
        resolved=resolved,
        pa=pa,
        assessment=assessment,
        score=score,
    )

    return {
        **row,
        "claim": claim_label,
        "claim_label": claim_label,
        "evidence_category": category,
        "evidence_category_label": _EVIDENCE_CATEGORY_LABELS.get(category, category),
        "relevance_score": score,
        "relevance_explanation": explanation,
        "display_tier": "primary" if score >= PRIMARY_RELEVANCE_THRESHOLD else "additional",
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


def _uploaded_fact_label(claim: str) -> str:
    if ":" in claim:
        label, value = claim.split(":", 1)
        return f"Uploaded fact: {label.strip().lower()} — {value.strip()}"
    return f"Uploaded fact: {claim}"


def _legal_citation_label(resolved: dict, pa: dict) -> str:
    section = (resolved.get("section") or "").lower()
    excerpt = (resolved.get("excerpt") or "").lower()
    source = (resolved.get("source_label") or "").lower()
    risk = pa.get("risk_tier", "")

    if "article 3" in section or ("definition" in source and "ai system" in source):
        return "AI system definition"
    if "article 5" in section or "prohibited" in source or "prohibited" in excerpt:
        return "Prohibited-practice check"
    if "annex iii" in section or "annex iii" in excerpt:
        return "High-risk / Annex III check"
    if "article 6" in section or ("high-risk" in excerpt and "annex" in excerpt):
        return "High-risk / Annex III check"
    if "article 50" in section or "transparency" in excerpt:
        return "Transparency obligations check"
    if "gpai" in excerpt or "general-purpose" in excerpt or "general purpose" in excerpt:
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


def _score_relevance(
    *,
    claim_type: str,
    claim_label: str,
    row: dict,
    resolved: dict,
    pa: dict,
    assessment: dict,
) -> int:
    excerpt = (resolved.get("excerpt") or "").lower()
    if not excerpt:
        return 25

    if claim_type == "uploaded_fact":
        return _score_uploaded_fact(row.get("claim", ""), excerpt)

    if claim_type == "governance":
        obs = row.get("claim", "").lower()
        overlap = sum(1 for w in _keywords(obs) if w in excerpt)
        return min(95, 50 + overlap * 12)

    return _score_legal_citation(claim_label, excerpt, pa, assessment)


def _score_uploaded_fact(claim: str, excerpt: str) -> int:
    if ":" not in claim:
        return 60
    _, value = claim.split(":", 1)
    value_words = _keywords(value)
    if not value_words:
        return 55
    matches = sum(1 for w in value_words if w in excerpt)
    ratio = matches / max(len(value_words), 1)
    return min(98, int(45 + ratio * 55))


def _score_legal_citation(claim_label: str, excerpt: str, pa: dict, assessment: dict) -> int:
    risk = pa.get("risk_tier", "")
    label_lower = claim_label.lower()
    score = 50

    if "annex iii" in label_lower or "high-risk" in label_lower:
        if "annex iii" in excerpt or "high-risk" in excerpt or "high risk" in excerpt:
            score += 25
        else:
            score -= 15

    if "ai system definition" in label_lower:
        if "ai system" in excerpt and ("infer" in excerpt or "learning" in excerpt or "model" in excerpt):
            score += 30
        else:
            score -= 10

    if "prohibited" in label_lower:
        if "prohibited" in excerpt or "unacceptable" in excerpt:
            score += 30
        else:
            score -= 10

    if "safety-component" in label_lower:
        if "safety component" in excerpt:
            score += 35
        else:
            score -= 5

    use_summary = (assessment.get("use_case_summary") or "").lower()
    facts = assessment.get("extracted_facts") or {}
    sector = (facts.get("sector") or {}).get("value", "").lower()
    context_blob = f"{use_summary} {sector}"

    industrial_signals = any(k in context_blob for k in ("maintenance", "machinery", "industrial", "sensor", "engine", "equipment"))
    persons_signals = any(k in excerpt for k in ("natural persons", "profiling", "employment", "recruit", "candidate", "worker"))

    if industrial_signals and persons_signals and "annex iii" in label_lower:
        score -= 25

    if risk in ("minimal_risk", "unclear"):
        if "shall always be considered high-risk" in excerpt or "profiling of natural persons" in excerpt:
            score -= 20
        if "does not show" in (pa.get("reasoning") or "").lower() or "uncertain" in (pa.get("reasoning") or "").lower():
            score += 10

    if risk == "high_risk_candidate" and "high-risk" in excerpt:
        score += 20

    return max(10, min(98, score))


def _keywords(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z]{4,}", (text or "").lower())
    stop = {"that", "this", "with", "from", "have", "been", "were", "their", "which", "about", "unclear"}
    return [w for w in words if w not in stop][:12]


def _build_relevance_explanation(
    *,
    claim_type: str,
    claim_label: str,
    row: dict,
    resolved: dict,
    pa: dict,
    assessment: dict,
    score: int,
) -> str:
    risk = pa.get("risk_tier", "")
    use_summary = (assessment.get("use_case_summary") or "").strip()

    if claim_type == "uploaded_fact":
        if ":" in row.get("claim", ""):
            _, value = row["claim"].split(":", 1)
            return (
                f"The uploaded document supports the fact \"{value.strip()}\". "
                f"The cited excerpt describes this directly from the user-provided material."
            )
        return "This excerpt comes from an uploaded document cited as factual evidence for the assessment."

    if claim_type == "governance":
        return (
            "This source was cited in support of a governance observation. "
            "Review whether the excerpt matches the specific compliance area discussed."
        )

    label_lower = claim_label.lower()
    context_snippet = use_summary[:120] + ("..." if len(use_summary) > 120 else "") if use_summary else "this use case"

    if "ai system definition" in label_lower:
        return (
            f"This excerpt sets out criteria for what counts as an AI system under the EU AI Act. "
            f"The assessment compared those criteria to {context_snippet}."
        )

    if "prohibited" in label_lower:
        return (
            "This regulatory excerpt describes prohibited AI practices. "
            "The assessment checked whether the uploaded use case falls within any prohibition."
        )

    if "annex iii" in label_lower or "high-risk" in label_lower:
        if score < PRIMARY_RELEVANCE_THRESHOLD:
            return (
                "This excerpt describes high-risk conditions or Annex III categories in the AI Act. "
                "It is relevant background law, but it does not by itself prove this system is high-risk; "
                f"the assessment still had to infer how it applies to {context_snippet}."
            )
        if risk in ("minimal_risk", "unclear"):
            return (
                "This Annex III / high-risk excerpt was used for comparison. "
                "The uploaded documents do not clearly show the system meets those high-risk triggers, so the assessment "
                f"concluded {risk.replace('_', ' ')} rather than confirmed high-risk."
            )
        return (
            "This excerpt lists or defines high-risk conditions. "
            "The assessment linked it to uploaded facts suggesting the system may fall within Annex III."
        )

    if "safety-component" in label_lower:
        return (
            "This excerpt concerns safety components of products. "
            "The assessment checked whether the AI model is integrated as such a component."
        )

    if score < PRIMARY_RELEVANCE_THRESHOLD:
        return (
            "This regulatory excerpt was retrieved during assessment but has weak direct alignment "
            "with the specific claim. Treat it as background context, not proof of the conclusion."
        )

    return (
        "This regulatory excerpt provides legal context used during classification. "
        "The final risk tier is still a system inference; see 'System inference' above."
    )
