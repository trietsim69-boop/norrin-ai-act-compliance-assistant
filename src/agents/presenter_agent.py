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

def presenter_agent(pipeline_result: dict) -> dict:
    """
    Format a pipeline result into display-ready dashboard data.

    Args:
        pipeline_result: the dict returned by run_assessment_pipeline (must contain
            'assessment' and 'critic' keys; '_meta' and 'history' are optional).

    Returns:
        A dict with:
            - sections: dict of 6 dashboard sections
            - warnings: list of {severity, message}
            - disclaimer: legal disclaimer string
            - _meta: forwarded + augmented metadata
    """
    assessment = pipeline_result.get("assessment") or {}
    critic = pipeline_result.get("critic") or {}
    meta_in = pipeline_result.get("_meta", {})

    sections = {
        "use_case_summary":        _section_summary(assessment),
        "extracted_facts":         _section_facts(assessment),
        "preliminary_assessment":  _section_assessment(assessment),
        "governance_observations": _section_governance(assessment),
        "missing_information":     _section_missing(assessment, critic),
        "citations":               _section_citations(assessment),
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


def _section_facts(a: dict) -> dict:
    raw = a.get("extracted_facts") or {}
    facts = []
    for key, label in FACT_LABELS.items():
        fact = raw.get(key) or {}
        confidence = fact.get("confidence", "low")
        facts.append({
            "key":              key,
            "label":            label,
            "value":            (fact.get("value") or "Unclear").strip(),
            "confidence":       confidence,
            "confidence_color": CONFIDENCE_COLORS.get(confidence, "grey"),
            "evidence":         list(fact.get("evidence") or []),
        })

    extra_keys = [k for k in raw.keys() if k not in FACT_LABELS]
    for key in extra_keys:
        fact = raw.get(key) or {}
        confidence = fact.get("confidence", "low")
        facts.append({
            "key":              key,
            "label":            key.replace("_", " ").title(),
            "value":            (fact.get("value") or "Unclear").strip(),
            "confidence":       confidence,
            "confidence_color": CONFIDENCE_COLORS.get(confidence, "grey"),
            "evidence":         list(fact.get("evidence") or []),
        })

    return {"title": "Extracted facts", "facts": facts}


def _section_assessment(a: dict) -> dict:
    pa = a.get("preliminary_assessment") or {}
    ai_value = pa.get("ai_system", "unclear")
    risk_value = pa.get("risk_tier", "unclear")
    confidence = pa.get("confidence", "low")

    ai_label, ai_color = AI_SYSTEM_LABELS.get(ai_value, (ai_value, "grey"))
    risk_label, risk_color = RISK_TIER_LABELS.get(risk_value, (risk_value, "grey"))

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
        "legal_citations": list(pa.get("legal_citations") or []),
    }


def _section_governance(a: dict) -> dict:
    items = []
    for obs in a.get("governance_observations") or []:
        area = obs.get("area", "")
        items.append({
            "area":         area,
            "area_label":   GOVERNANCE_AREA_LABELS.get(area, area.replace("_", " ").title() or "General"),
            "observation":  (obs.get("observation") or "").strip(),
            "citations":    list(obs.get("citations") or []),
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


def _section_citations(a: dict) -> dict:
    uploaded_ids: set[str] = set()
    corpus_ids: set[str] = set()

    pa = a.get("preliminary_assessment") or {}
    for cid in pa.get("legal_citations") or []:
        _bucket(cid, uploaded_ids, corpus_ids)

    for fact in (a.get("extracted_facts") or {}).values():
        if isinstance(fact, dict):
            for cid in fact.get("evidence") or []:
                _bucket(cid, uploaded_ids, corpus_ids)

    for obs in a.get("governance_observations") or []:
        for cid in obs.get("citations") or []:
            _bucket(cid, uploaded_ids, corpus_ids)

    return {
        "title": "Citations and evidence separation",
        "uploaded_evidence": [{"chunk_id": c} for c in sorted(uploaded_ids)],
        "corpus_citations":  [{"chunk_id": c} for c in sorted(corpus_ids)],
    }


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bucket(chunk_id: str, uploaded: set[str], corpus: set[str]) -> None:
    if not chunk_id:
        return
    cid = chunk_id.strip()
    lower = cid.lower()
    if lower.startswith("corpus") or "annex" in lower or "article" in lower:
        corpus.add(cid)
    else:
        uploaded.add(cid)
