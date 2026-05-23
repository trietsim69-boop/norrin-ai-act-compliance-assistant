"""
Presenter Agent — turns the reviewed assessment into display-ready dashboard data.

Design note: by deliberate choice, the Presenter does NOT call an LLM. The MVP plan
explicitly forbids the Presenter from introducing new legal reasoning, so the cleanest
and safest implementation is a deterministic, programmatic formatter. This also makes
the dashboard render instantly (no API latency) and zero-cost.

The autonomy of this agent lies in formatting decisions — which severity to highlight,
which warnings to surface, how to group governance items, how to colour confidence
levels, how to separate uploaded evidence from corpus evidence.

Input:  the dict returned by src.pipeline.run_assessment_pipeline (without "presented")
Output: a "presented" dict with display-ready sections, warnings, and a disclaimer.
"""

from __future__ import annotations

from typing import Any

from src.citation_relevance import enrich_citation_row, build_system_inference

DISCLAIMER = (
    "This is a preliminary, AI-generated assessment for structured review. "
    "It is NOT legal advice and does not replace qualified legal counsel. "
    "Always have a human expert validate findings before any deployment decision."
)

RISK_TIER_LABELS = {
    "prohibited":           ("Prohibited practice — unacceptable risk", "red"),
    "high_risk_candidate":  ("High-risk candidate (Annex III)",         "orange"),
    "limited_risk":         ("Limited risk (transparency obligations)", "amber"),
    "minimal_risk":         ("Minimal risk",                            "green"),
    "gpai_obligations":     ("GPAI obligations apply",                  "blue"),
    "unclear":              ("Unclear — insufficient evidence",         "grey"),
}

AI_SYSTEM_LABELS = {
    "yes":     ("Meets AI system definition",       "green"),
    "no":      ("Does not meet AI system definition", "grey"),
    "unclear": ("Unclear",                          "amber"),
}

CONFIDENCE_COLORS = {
    "high":   "green",
    "medium": "amber",
    "low":    "red",
}

GOVERNANCE_AREA_LABELS = {
    "documentation":   "Documentation",
    "risk_management": "Risk management",
    "transparency":    "Transparency",
    "human_oversight": "Human oversight",
    "monitoring":      "Monitoring & logging",
    "accountability":  "Accountability",
    "role_clarity":    "Role clarity (provider/deployer)",
}

FACT_LABELS = {
    "purpose":          "Purpose",
    "affected_persons": "Affected persons",
    "sector":           "Sector",
    "automation_level": "Automation level",
    "human_oversight":  "Human oversight",
    "uses_gpai":        "Uses GPAI",
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def presenter_agent(pipeline_result: dict, chunk_lookup: dict | None = None) -> dict:
    """
    Format a pipeline result into display-ready dashboard data.

    Args:
        pipeline_result: dict from run_assessment_pipeline (assessment + critic).
        chunk_lookup: optional map chunk_id -> resolved citation card from
            src.citation_resolver.resolve_citations.
    """
    assessment = pipeline_result.get("assessment") or {}
    critic = pipeline_result.get("critic") or {}
    meta_in = pipeline_result.get("_meta", {})
    lookup = chunk_lookup or {}

    sections = {
        "use_case_summary":        _section_summary(assessment),
        "extracted_facts":         _section_facts(assessment, lookup),
        "preliminary_assessment":  _section_assessment(assessment, lookup),
        "governance_observations": _section_governance(assessment, lookup),
        "missing_information":     _section_missing(assessment, critic),
        "citations":               _section_citations(assessment, lookup),
    }

    warnings = _build_warnings(assessment, critic)

    return {
        "sections": sections,
        "warnings": warnings,
        "disclaimer": DISCLAIMER,
        "_meta": {
            **meta_in,
            "critic_pass": bool(critic.get("pass", False)),
            "critic_issue_count": len(critic.get("issues") or []),
            "sections_present": list(sections.keys()),
        },
    }


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _section_summary(a: dict) -> dict:
    return {
        "title": "Use-case summary",
        "body": (a.get("use_case_summary") or "").strip() or "_(no summary produced)_",
    }


def _section_facts(a: dict, lookup: dict) -> dict:
    raw = a.get("extracted_facts") or {}
    facts = []

    def _build(key: str, label: str, fact: dict) -> dict:
        confidence = fact.get("confidence", "low")
        evidence_ids = list(fact.get("evidence") or [])
        return {
            "key": key,
            "label": label,
            "value": (fact.get("value") or "Unclear").strip(),
            "confidence": confidence,
            "confidence_color": CONFIDENCE_COLORS.get(confidence, "grey"),
            "evidence": evidence_ids,
            "evidence_resolved": [_card_for(cid, lookup) for cid in evidence_ids],
        }

    for key, label in FACT_LABELS.items():
        facts.append(_build(key, label, raw.get(key) or {}))
    for key in [k for k in raw.keys() if k not in FACT_LABELS]:
        facts.append(_build(key, key.replace("_", " ").title(), raw.get(key) or {}))

    return {"title": "Extracted facts", "facts": facts}


def _section_assessment(a: dict, lookup: dict) -> dict:
    pa = a.get("preliminary_assessment") or {}
    ai_value = pa.get("ai_system", "unclear")
    risk_value = pa.get("risk_tier", "unclear")
    confidence = pa.get("confidence", "low")

    ai_label, ai_color = AI_SYSTEM_LABELS.get(ai_value, (ai_value, "grey"))
    risk_label, risk_color = RISK_TIER_LABELS.get(risk_value, (risk_value, "grey"))
    legal_ids = list(pa.get("legal_citations") or [])

    return {
        "title": "Preliminary EU AI Act assessment",
        "ai_system": {
            "value": ai_value,
            "label": ai_label,
            "color": ai_color,
            "reasoning": (pa.get("ai_system_reasoning") or "").strip(),
        },
        "risk_tier": {
            "value": risk_value,
            "label": risk_label,
            "color": risk_color,
        },
        "confidence": {
            "value": confidence,
            "color": CONFIDENCE_COLORS.get(confidence, "grey"),
        },
        "reasoning": (pa.get("reasoning") or "").strip(),
        "legal_citations": legal_ids,
        "legal_citations_resolved": [_card_for(cid, lookup) for cid in legal_ids],
    }


def _section_governance(a: dict, lookup: dict) -> dict:
    items = []
    for obs in a.get("governance_observations") or []:
        area = obs.get("area", "")
        cite_ids = list(obs.get("citations") or [])
        items.append({
            "area": area,
            "area_label": GOVERNANCE_AREA_LABELS.get(area, area.replace("_", " ").title() or "General"),
            "observation": (obs.get("observation") or "").strip(),
            "citations": cite_ids,
            "citations_resolved": [_card_for(cid, lookup) for cid in cite_ids],
        })
    return {"title": "Governance observations", "items": items}


def _section_missing(a: dict, critic: dict) -> dict:
    missing = []
    for m in a.get("missing_information") or []:
        missing.append({
            "topic":              (m.get("topic") or "").strip(),
            "why_it_matters":     (m.get("why_it_matters") or "").strip(),
            "suggested_question": (m.get("suggested_question") or "").strip(),
        })

    follow_ups: list[str] = []
    seen: set[str] = set()
    for q in critic.get("missing_questions") or []:
        q = (q or "").strip()
        if q and q not in seen:
            seen.add(q)
            follow_ups.append(q)
    for m in missing:
        q = m["suggested_question"]
        if q and q not in seen:
            seen.add(q)
            follow_ups.append(q)

    return {
        "title": "Missing information and follow-up questions",
        "missing": missing,
        "follow_up_questions": follow_ups,
    }


def _section_citations(a: dict, lookup: dict) -> dict:
    raw_rows: list[dict] = []

    pa = a.get("preliminary_assessment") or {}
    for cid in pa.get("legal_citations") or []:
        raw_rows.append(_claim_row(
            claim="Regulatory reference",
            resolved=_card_for(cid, lookup),
            claim_type="legal",
        ))

    for key, fact in (a.get("extracted_facts") or {}).items():
        if not isinstance(fact, dict):
            continue
        label = FACT_LABELS.get(key, key.replace("_", " ").title())
        value = (fact.get("value") or "Unclear").strip()
        for cid in fact.get("evidence") or []:
            raw_rows.append(_claim_row(
                claim=f"{label}: {value}",
                resolved=_card_for(cid, lookup),
                claim_type="uploaded_fact",
            ))

    for obs in a.get("governance_observations") or []:
        area = obs.get("area", "")
        area_label = GOVERNANCE_AREA_LABELS.get(area, area.replace("_", " ").title() or "Governance")
        observation = (obs.get("observation") or "").strip()
        claim = f"{area_label}: {observation[:120]}{'…' if len(observation) > 120 else ''}"
        for cid in obs.get("citations") or []:
            raw_rows.append(_claim_row(
                claim=claim,
                resolved=_card_for(cid, lookup),
                claim_type="governance",
            ))

    rows: list[dict] = []
    for r in raw_rows:
        claim_type = r.pop("_claim_type")
        rows.append(enrich_citation_row(r, claim_type=claim_type, assessment=a))
    primary = [r for r in rows if r.get("display_tier") == "primary"]
    additional = [r for r in rows if r.get("display_tier") != "primary"]

    uploaded_seen: dict[str, dict] = {}
    corpus_seen: dict[str, dict] = {}
    for row in rows:
        resolved = row.get("_resolved") or {}
        cid = resolved.get("chunk_id", row.get("chunk_id", ""))
        if _is_corpus_citation(resolved):
            corpus_seen.setdefault(cid, resolved)
        else:
            uploaded_seen.setdefault(cid, resolved)

    return {
        "title": "Citations and evidence separation",
        "system_inference": build_system_inference(a),
        "claims_table": primary,
        "citation_cards": primary,
        "additional_evidence": additional,
        "uploaded_evidence": list(uploaded_seen.values()),
        "corpus_citations": list(corpus_seen.values()),
    }


def _claim_row(*, claim: str, resolved: dict, claim_type: str) -> dict:
    return {
        "claim": claim,
        "source": resolved.get("source", resolved.get("source_label", "")),
        "evidence_type": resolved.get("evidence_type", "Unknown"),
        "excerpt": resolved.get("excerpt", ""),
        "chunk_id": resolved.get("chunk_id", ""),
        "found": resolved.get("found", False),
        "_resolved": resolved,
        "_claim_type": claim_type,
    }


def _card_for(chunk_id: str, lookup: dict) -> dict:
    if chunk_id in lookup:
        return lookup[chunk_id]
    from src.citation_resolver import resolve_citation
    return resolve_citation(chunk_id)


def _is_corpus_citation(resolved: dict) -> bool:
    st = resolved.get("source_type", "")
    if st in ("regulation", "official_guidance"):
        return True
    cid = (resolved.get("chunk_id") or "").lower()
    return cid.startswith("corpus") or "article" in cid or "annex" in cid


# ---------------------------------------------------------------------------
# Warnings — surfaced at the top of the dashboard
# ---------------------------------------------------------------------------

def _build_warnings(a: dict, critic: dict) -> list[dict]:
    warnings: list[dict] = []
    pa = a.get("preliminary_assessment") or {}
    risk = pa.get("risk_tier", "")
    confidence = pa.get("confidence", "")

    if risk == "prohibited":
        warnings.append({
            "severity": "high",
            "message": "Possible prohibited practice detected. Halt deployment pending legal review.",
        })
    elif risk == "high_risk_candidate":
        warnings.append({
            "severity": "medium",
            "message": "High-risk classification candidate. Full compliance obligations may apply.",
        })
    elif risk == "gpai_obligations":
        warnings.append({
            "severity": "medium",
            "message": "GPAI deployer obligations likely apply. Verify provider documentation.",
        })
    elif risk == "limited_risk":
        warnings.append({
            "severity": "low",
            "message": "Transparency obligations apply (Article 50).",
        })

    if confidence == "low":
        warnings.append({
            "severity": "low",
            "message": "Confidence is low — important facts are missing. See follow-up questions.",
        })

    if critic.get("pass") is False:
        warnings.append({
            "severity": "medium",
            "message": "Critic flagged unresolved issues — assessment may need expert review.",
        })

    return warnings


