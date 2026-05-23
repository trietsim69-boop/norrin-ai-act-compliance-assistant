"""
Critic Agent — quality gate for the Assessment Agent's output.

Responsibilities (from the MVP plan, section 5.3):
    - Decide whether the assessment passes or requires revision.
    - Decide which specific claims lack sufficient citation support.
    - Decide whether the confidence level is too high for the available evidence.
    - Decide what follow-up questions to generate based on what is missing.
    - Trigger one revision loop if pass = false (handled by src.pipeline).

Architecture: single structured LLM call. No retrieval, no ReAct loop. The critic
receives the assessment JSON and the same evidence chunks the Assessment Agent
saw, and emits a verdict.

Mock mode: when MOCK_LLM=true, the critic decides pass/fail deterministically
based on heuristics applied to the assessment (low confidence on a high-risk
claim, missing legal citations, etc.). Lets the whole pipeline run offline.
"""

from __future__ import annotations

import json
from typing import Any

from src.llm import call_llm
from src.citation_validation import (
    build_evidence_index,
    format_cited_chunks_for_critic,
)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

CRITIC_SYSTEM_PROMPT = """You are the Critic Agent in a multi-agent EU AI Act compliance review system.

Your job: evaluate the Assessment Agent's output for quality and grounding, and decide whether it should be accepted as-is or revised once.

EVALUATION CHECKLIST (run every check)
1. Required sections present: use_case_summary, extracted_facts, preliminary_assessment, governance_observations, missing_information.
2. Citation support: every major risk or legal claim cites a corpus chunk_id. Every extracted fact cites an uploaded chunk_id (or is flagged as missing).
3. Evidence separation: uploaded-document facts and EU AI Act references are kept separate (uploaded_chunks vs corpus_chunks).
4. Confidence calibration: confidence is "low" when key facts are missing or ambiguous. A "high" rating must be backed by clear, cited evidence.
5. Missing information: useful follow-up questions are generated for any genuinely missing facts.
6. Legal safety: no statements that read as final legal advice. Qualified language used ("appears to", "likely", "may fall within").
7. Source relevance: cited corpus chunks are actually relevant to the claimed risk category.
8. Contradictions: facts in the assessment do not contradict each other or the evidence.
9. Citation relevance: For each cited chunk_id, ask "Does this chunk DIRECTLY support the specific claim?"
   - Predictive maintenance must NOT cite employment/recruitment Annex III as primary support for minimal risk.
   - HR screening SHOULD cite employment/recruitment Annex III for high-risk reasoning.
   - GPAI claims require evidence of foundation model / third-party LLM use — custom LSTM alone is NOT GPAI.
   - Minimal risk claims must explain why Annex III categories are NOT met, not cite unrelated high-risk lists.
10. Source type separation: corpus chunk_ids must not appear in extracted_facts.evidence; uploaded chunk_ids must not be sole support for legal_citations.
11. Over-citation: flag chunk_ids cited only because they appeared in retrieval, not because they prove the claim.

AUTONOMOUS DECISIONS YOU MAKE
- Decide pass vs fail.
- Identify which specific claims are unsupported, overconfident, or contradicted.
- Draft a single concrete revision_instruction the Assessment Agent can act on.
- Generate the missing_questions an expert would ask next.

OUTPUT — a single valid JSON object with EXACTLY this shape:

{
  "pass": true | false,
  "issues": [
    {"category": "citation|confidence|legal_safety|contradiction|missing_section|relevance|citation_relevance",
     "claim": "...",
     "problem": "...",
     "severity": "low|medium|high"}
  ],
  "revision_instruction": "single concrete instruction for the Assessment Agent, or empty string if pass=true",
  "missing_questions": [
    "question 1",
    "question 2"
  ]
}

Set pass=true only when the assessment is well-grounded, properly cited, and appropriately qualified. When in doubt, fail it and request a revision.
"""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def critic_agent(
    assessment: dict,
    uploaded_chunks: list[dict] | None = None,
    corpus_chunks: list[dict] | None = None,
) -> dict:
    """
    Review an assessment and return a pass/fail verdict plus revision instructions.
    """
    user_msg = _build_user_message(
        assessment=assessment,
        uploaded_chunks=uploaded_chunks or [],
        corpus_chunks=corpus_chunks or [],
    )

    raw = call_llm(
        messages=[
            {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        response_format="json",
        temperature=0.1,
        max_tokens=1500,
        mock=_pick_mock_fixture(assessment),
    )

    result = _safe_json_loads(raw["content"])
    result.setdefault("pass", False)
    result.setdefault("issues", [])
    result.setdefault("revision_instruction", "")
    result.setdefault("missing_questions", [])
    return result


# ---------------------------------------------------------------------------
# Prompt construction helpers
# ---------------------------------------------------------------------------

def _build_user_message(
    *,
    assessment: dict,
    uploaded_chunks: list[dict],
    corpus_chunks: list[dict],
) -> str:
    parts: list[str] = []

    parts.append("## Assessment to review")
    parts.append(json.dumps(assessment, indent=2, ensure_ascii=False))

    parts.append("## Available uploaded chunk_ids (for citation validation)")
    parts.append(_format_chunk_index(uploaded_chunks))

    parts.append("## Available corpus chunk_ids (for citation validation)")
    parts.append(_format_chunk_index(corpus_chunks))

    evidence_index = build_evidence_index(uploaded_chunks, corpus_chunks)
    parts.append("## Cited chunk text (verify direct support for each claim)")
    parts.append(format_cited_chunks_for_critic(assessment, evidence_index))

    parts.append(
        "## Instructions\n"
        "Run the evaluation checklist. Identify every concrete issue. "
        "Decide pass/fail. If failing, draft ONE actionable revision_instruction. "
        "Always include at least 1-2 missing_questions a human expert would ask next."
    )
    return "\n\n".join(parts)


def _format_chunk_index(chunks: list[dict]) -> str:
    if not chunks:
        return "(none)"
    lines = []
    for c in chunks[:50]:
        cid = c.get("chunk_id", "?")
        meta = []
        if c.get("filename"):
            meta.append(c["filename"])
        if c.get("section"):
            meta.append(c["section"])
        suffix = f" — {' · '.join(meta)}" if meta else ""
        lines.append(f"- {cid}{suffix}")
    if len(chunks) > 50:
        lines.append(f"- ... ({len(chunks) - 50} more)")
    return "\n".join(lines)


def _safe_json_loads(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {"_parse_error": "empty response"}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if 0 <= start < end:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {"_parse_error": "invalid JSON", "_raw": text[:500]}


# ---------------------------------------------------------------------------
# Mock fixtures — used when MOCK_LLM=true
# ---------------------------------------------------------------------------

def _pick_mock_fixture(assessment: dict) -> dict:
    """
    Deterministic critic for mock mode. Fails the assessment if any of these
    quality issues are detected; otherwise passes.
    """
    issues: list[dict] = []
    missing_questions: list[str] = []

    if assessment.get("_meta", {}).get("was_revision"):
        return _ok_fixture(
            missing_questions=_default_followups(assessment),
            note="Revised assessment looks acceptable.",
        )

    pa = assessment.get("preliminary_assessment", {}) or {}
    risk_tier = pa.get("risk_tier", "")
    confidence = pa.get("confidence", "")
    legal_citations = pa.get("legal_citations") or []

    # Heuristic 1: high-stakes classification with no legal citation
    if risk_tier in ("prohibited", "high_risk_candidate") and not legal_citations:
        issues.append({
            "category": "citation",
            "claim": f"risk_tier = {risk_tier}",
            "problem": "No legal citation supports the risk classification.",
            "severity": "high",
        })

    # Heuristic 2: prohibited claim is high-confidence (should always be cautious)
    if risk_tier == "prohibited" and confidence == "high":
        issues.append({
            "category": "confidence",
            "claim": "risk_tier = prohibited at high confidence",
            "problem": "Prohibited-practice findings should be stated cautiously and recommend legal review.",
            "severity": "high",
        })

    # Heuristic 3: required top-level keys missing
    required = ("use_case_summary", "extracted_facts", "preliminary_assessment",
                "governance_observations", "missing_information")
    for key in required:
        if key not in assessment:
            issues.append({
                "category": "missing_section",
                "claim": key,
                "problem": f"Required section '{key}' is absent.",
                "severity": "high",
            })

    # Heuristic 4: an extracted fact at high confidence with no evidence
    facts = assessment.get("extracted_facts") or {}
    for name, fact in facts.items():
        if isinstance(fact, dict) and fact.get("confidence") == "high" and not fact.get("evidence"):
            issues.append({
                "category": "citation",
                "claim": f"extracted_facts.{name}",
                "problem": "Stated at high confidence but no evidence chunk_id is cited.",
                "severity": "medium",
            })

    # Heuristic 5: corpus chunk_ids in uploaded fact evidence
    for name, fact in facts.items():
        if not isinstance(fact, dict):
            continue
        for cid in fact.get("evidence") or []:
            if str(cid).lower().startswith("corpus"):
                issues.append({
                    "category": "citation_relevance",
                    "claim": f"extracted_facts.{name}",
                    "problem": "Corpus chunk cited as support for an uploaded-system fact.",
                    "severity": "high",
                })

    # Heuristic 6: industrial/maintenance case citing employment Annex III for minimal risk
    use_summary = (assessment.get("use_case_summary") or "").lower()
    sector = (facts.get("sector") or {}).get("value", "").lower()
    context = f"{use_summary} {sector}"
    industrial = any(k in context for k in ("maintenance", "machinery", "industrial", "sensor", "predictive"))
    if industrial and risk_tier in ("minimal_risk", "unclear"):
        for cid in legal_citations:
            cid_lower = str(cid).lower()
            if any(k in cid_lower for k in ("employment", "recruit", "annex_iii")):
                issues.append({
                    "category": "citation_relevance",
                    "claim": "legal_citations for minimal-risk industrial case",
                    "problem": (
                        "Employment/recruitment Annex III citation is weak support for "
                        "predictive maintenance minimal-risk reasoning."
                    ),
                    "severity": "medium",
                })
                break

    # Heuristic 7: GPAI risk tier without GPAI evidence in facts
    if risk_tier == "gpai_obligations":
        gpai_val = (facts.get("uses_gpai") or {}).get("value", "").lower()
        if not any(k in gpai_val for k in ("gpai", "llm", "gpt", "foundation", "general-purpose", "general purpose")):
            issues.append({
                "category": "citation_relevance",
                "claim": "risk_tier = gpai_obligations",
                "problem": "GPAI obligations claimed but uploaded facts do not mention GPAI/LLM/foundation models.",
                "severity": "high",
            })

    # Heuristic 8: custom LSTM labeled as GPAI in uses_gpai fact
    gpai_val = (facts.get("uses_gpai") or {}).get("value", "").lower()
    if "lstm" in gpai_val and "gpai" in gpai_val and "foundation" not in gpai_val and "llm" not in gpai_val:
        issues.append({
            "category": "citation_relevance",
            "claim": "extracted_facts.uses_gpai",
            "problem": "Custom LSTM should not be labeled as GPAI without foundation-model evidence.",
            "severity": "medium",
        })

    # Always surface useful follow-up questions
    missing_questions = _default_followups(assessment)

    if not issues:
        return _ok_fixture(missing_questions=missing_questions, note="Looks well-grounded.")

    instruction = _draft_revision_instruction(issues, risk_tier)
    return _fixture({
        "pass": False,
        "issues": issues,
        "revision_instruction": instruction,
        "missing_questions": missing_questions,
    })


def _default_followups(assessment: dict) -> list[str]:
    out: list[str] = []
    for item in (assessment.get("missing_information") or []):
        q = item.get("suggested_question")
        if q:
            out.append(q)
    if not out:
        out = [
            "Who reviews the AI's output before it affects a person?",
            "What is the specific deployment context (sector, geography, scale)?",
        ]
    return out[:5]


def _draft_revision_instruction(issues: list[dict], risk_tier: str) -> str:
    if any(i["category"] == "citation_relevance" for i in issues):
        return (
            "Remove or replace citations that do not DIRECTLY support each claim. "
            "Do not cite employment/recruitment Annex III for industrial predictive maintenance. "
            "Do not use corpus chunks for uploaded facts or uploaded chunks for legal rules. "
            "Lower confidence where direct support is missing."
        )
    if any(i["category"] == "citation" for i in issues):
        return (
            "Attach explicit corpus chunk_ids to every legal claim, lower the "
            f"confidence on the {risk_tier or 'risk'} classification, and add "
            "qualifying language ('appears to', 'may fall within')."
        )
    if any(i["category"] == "confidence" for i in issues):
        return (
            "Lower the confidence on prohibited-practice findings and "
            "explicitly recommend legal review before any deployment decision."
        )
    if any(i["category"] == "missing_section" for i in issues):
        return (
            "Re-emit the full JSON with every required top-level section present."
        )
    return "Address the listed issues and re-emit the full JSON assessment."


def _fixture(d: dict) -> dict:
    return {"content": json.dumps(d, ensure_ascii=False), "tool_calls": None}


def _ok_fixture(*, missing_questions: list[str], note: str) -> dict:
    return _fixture({
        "pass": True,
        "issues": [{
            "category": "relevance",
            "claim": "overall",
            "problem": note,
            "severity": "low",
        }],
        "revision_instruction": "",
        "missing_questions": missing_questions,
    })
