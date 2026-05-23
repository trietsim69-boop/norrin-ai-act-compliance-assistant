"""
Trigger-based evaluation for demo cases.

Loads sample documents from demo_cases/, runs the assessment pipeline, and checks
whether the expected AI Act reasoning path was triggered (risk direction, domain
signals, follow-up questions, citations).

Run all cases:
    python -m scripts.run_trigger_tests

Run one case:
    python -m scripts.run_trigger_tests --case hr_screening
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from src.config import DEMO_CASES_DIR, ROOT_DIR
from src.chunking import chunk_document
from src.vector_store import add_chunks_to_uploaded, delete_session_chunks
from src.pipeline import run_assessment_pipeline

EXPECTED_TRIGGERS_PATH = ROOT_DIR / "tests" / "expected_triggers.json"

RISK_DIRECTION_ALIASES: dict[str, set[str]] = {
    "high_risk": {"high_risk", "high_risk_candidate", "high-risk", "high risk"},
    "limited_risk": {"limited_risk", "limited-risk", "limited risk"},
    "prohibited_or_unacceptable": {
        "prohibited",
        "prohibited_or_unacceptable",
        "unacceptable",
        "unacceptable_risk",
    },
    "minimal_risk": {"minimal_risk", "minimal-risk", "minimal risk", "minimal"},
    "gpai_obligations": {"gpai_obligations", "gpai", "gpai-related"},
    "unclear": {"unclear", "unknown"},
}

TRIGGER_KEYWORDS: dict[str, tuple[str, ...]] = {
    "employment": ("employment", "recruit", "recruitment", "hiring", "applicant", "annex iii"),
    "chatbot": ("chatbot", "article 50", "transparency", "interact", "virtual assistant"),
    "emotion recognition workplace": (
        "emotion",
        "workplace",
        "article 5",
        "prohibited",
        "worker",
        "employee",
    ),
    "narrow filtering": ("spam", "filter", "minimal", "narrow", "procedural"),
    "GPAI third-party": ("gpai", "llm", "gpt", "third-party", "deployer", "chapter v", "provider"),
}


def load_expected_triggers(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or EXPECTED_TRIGGERS_PATH
    return json.loads(path.read_text(encoding="utf-8"))


def list_demo_case_slugs() -> list[str]:
    if not DEMO_CASES_DIR.is_dir():
        return []
    return sorted(
        p.name for p in DEMO_CASES_DIR.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )


def load_demo_case_documents(case_slug: str) -> list[dict]:
    """Return preprocessing-shaped doc dicts for every .md/.txt in a demo folder."""
    case_dir = DEMO_CASES_DIR / case_slug
    if not case_dir.is_dir():
        raise FileNotFoundError(f"Demo case folder not found: {case_dir}")

    session_id = f"demo_{case_slug}"
    docs: list[dict] = []

    for path in sorted(case_dir.iterdir()):
        if path.suffix.lower() not in {".md", ".txt"}:
            continue
        docs.append(
            {
                "filename": path.name,
                "session_id": session_id,
                "markdown_path": str(path),
                "document_type": _infer_demo_document_type(path.name),
                "source_type": "demo_case",
                "error": None,
            }
        )

    if not docs:
        raise ValueError(f"No .md/.txt documents in {case_dir}")

    return docs


def ingest_demo_case(case_slug: str, session_id: str | None = None) -> tuple[str, list[dict]]:
    """Chunk and index demo documents; returns (session_id, chunks)."""
    session_id = session_id or f"demo_{case_slug}_{uuid.uuid4().hex[:8]}"
    delete_session_chunks(session_id)

    docs = load_demo_case_documents(case_slug)
    for doc in docs:
        doc["session_id"] = session_id

    chunks: list[dict] = []
    for doc in docs:
        chunks.extend(chunk_document(doc))

    add_chunks_to_uploaded(chunks)
    return session_id, chunks


def run_demo_case_pipeline(
    case_slug: str,
    *,
    session_metadata: dict | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    session_id, _chunks = ingest_demo_case(case_slug, session_id=session_id)
    meta = {"case_name": case_slug, **(session_metadata or {})}
    result = run_assessment_pipeline(session_id, session_metadata=meta)
    result["_eval_session_id"] = session_id
    return result


def evaluate_pipeline_result(
    result: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    """Score one pipeline run against an expected_triggers entry."""
    checks: list[dict[str, Any]] = []
    assessment = result.get("assessment") or {}
    critic = result.get("critic") or {}
    pa = assessment.get("preliminary_assessment") or {}

    risk_tier = str(pa.get("risk_tier", "")).strip()
    expected_risk = expected.get("expected_risk_direction", "")
    checks.append(_check_risk_direction(risk_tier, expected_risk))

    trigger = expected.get("expected_trigger", "")
    checks.append(_check_domain_trigger(trigger, assessment, result))

    for phrase in expected.get("must_ask_about") or []:
        checks.append(_check_follow_up_question(phrase, assessment, critic))

    min_cites = int(expected.get("min_legal_citations", 0))
    legal_citations = pa.get("legal_citations") or []
    checks.append({
        "name": "legal_citations",
        "passed": len(legal_citations) >= min_cites,
        "detail": f"Found {len(legal_citations)} legal citation(s); need >= {min_cites}.",
    })

    if expected.get("expect_critic_stage", True):
        history = result.get("history") or []
        has_critic = any(h.get("stage", "").startswith("critic") for h in history)
        checks.append({
            "name": "critic_stage",
            "passed": has_critic,
            "detail": "Critic agent ran" if has_critic else "No critic stage in pipeline history.",
        })

    checks.append(_check_required_sections(assessment))

    passed = all(c["passed"] for c in checks)
    return {
        "case_slug": expected.get("case_slug"),
        "case_name": expected.get("case_name"),
        "passed": passed,
        "checks": checks,
        "observed_risk_tier": risk_tier,
        "observed_confidence": pa.get("confidence"),
        "revision_triggered": (result.get("_meta") or {}).get("revision_triggered"),
    }


def run_trigger_test(expected: dict[str, Any]) -> dict[str, Any]:
    case_slug = expected["case_slug"]
    session_id: str | None = None
    try:
        session_id, _ = ingest_demo_case(case_slug)
        meta = {"case_name": expected.get("case_name") or case_slug}
        result = run_assessment_pipeline(session_id, session_metadata=meta)
        result["_eval_session_id"] = session_id
        verdict = evaluate_pipeline_result(result, expected)
        verdict["error"] = None
        return verdict
    except Exception as exc:
        return {
            "case_slug": case_slug,
            "case_name": expected.get("case_name"),
            "passed": False,
            "checks": [],
            "error": str(exc),
        }
    finally:
        if session_id:
            delete_session_chunks(session_id)


def run_all_trigger_tests(
    *,
    case_filter: str | None = None,
    triggers_path: Path | None = None,
) -> dict[str, Any]:
    expected_list = load_expected_triggers(triggers_path)
    if case_filter:
        expected_list = [e for e in expected_list if e.get("case_slug") == case_filter]
        if not expected_list:
            raise ValueError(f"No expected trigger entry for case_slug={case_filter!r}")

    results = [run_trigger_test(e) for e in expected_list]
    passed_count = sum(1 for r in results if r.get("passed"))
    return {
        "total": len(results),
        "passed": passed_count,
        "failed": len(results) - passed_count,
        "all_passed": passed_count == len(results),
        "results": results,
    }


# ---------------------------------------------------------------------------
# Internal check helpers
# ---------------------------------------------------------------------------

def _check_risk_direction(observed: str, expected: str) -> dict[str, Any]:
    aliases = RISK_DIRECTION_ALIASES.get(expected, {expected})
    normalized = observed.lower().replace("-", "_").replace(" ", "_")
    ok = normalized in {a.lower().replace("-", "_").replace(" ", "_") for a in aliases}
    return {
        "name": "risk_direction",
        "passed": ok,
        "detail": f"Observed risk_tier={observed!r}; expected {expected!r}.",
    }


def _check_domain_trigger(
    trigger: str,
    assessment: dict,
    result: dict,
) -> dict[str, Any]:
    keywords = TRIGGER_KEYWORDS.get(trigger, (trigger.lower(),))
    blob = _assessment_text_blob(assessment, result).lower()
    matched = [kw for kw in keywords if kw.lower() in blob]
    ok = len(matched) >= min(2, len(keywords)) if len(keywords) > 2 else bool(matched)
    if len(keywords) == 1:
        ok = bool(matched)
    return {
        "name": "domain_trigger",
        "passed": ok,
        "detail": f"Trigger {trigger!r}: matched {matched or 'none'} in assessment/corpus context.",
    }


def _check_follow_up_question(
    phrase: str,
    assessment: dict,
    critic: dict,
) -> dict[str, Any]:
    blob = _follow_up_blob(assessment, critic)
    ok = _phrase_matches(phrase, blob)
    return {
        "name": f"follow_up:{phrase}",
        "passed": ok,
        "detail": f"Must ask about {phrase!r}: {'found' if ok else 'not found'} in assessment follow-ups.",
    }


def _check_required_sections(assessment: dict) -> dict[str, Any]:
    required = (
        "use_case_summary",
        "extracted_facts",
        "preliminary_assessment",
        "governance_observations",
        "missing_information",
    )
    missing = [k for k in required if k not in assessment]
    return {
        "name": "required_sections",
        "passed": not missing,
        "detail": "All required sections present."
        if not missing
        else f"Missing sections: {', '.join(missing)}",
    }


def _assessment_text_blob(assessment: dict, result: dict) -> str:
    parts: list[str] = [
        assessment.get("use_case_summary") or "",
        json.dumps(assessment.get("extracted_facts") or {}),
        json.dumps(assessment.get("preliminary_assessment") or {}),
    ]
    for stage in result.get("history") or []:
        if stage.get("stage") == "assessment_v1":
            parts.append(json.dumps(stage.get("output") or {}))
    return " ".join(parts)


def _follow_up_blob(assessment: dict, critic: dict) -> str:
    parts: list[str] = [" ".join(_collect_questions(assessment, critic))]
    parts.append(assessment.get("use_case_summary") or "")
    pa = assessment.get("preliminary_assessment") or {}
    parts.append(pa.get("reasoning") or "")
    for item in assessment.get("missing_information") or []:
        parts.append(json.dumps(item))
    for obs in assessment.get("governance_observations") or []:
        parts.append(json.dumps(obs))
    return " ".join(parts).lower()


def _phrase_matches(phrase: str, blob: str) -> bool:
    blob = blob.lower()
    if phrase.lower() in blob:
        return True
    tokens = [t for t in re.split(r"[^a-z0-9]+", phrase.lower()) if len(t) > 2]
    if not tokens:
        return False
    # Ignore generic question words when matching multi-word phrases.
    skip = {"what", "the", "and", "for", "how", "does", "your"}
    tokens = [t for t in tokens if t not in skip]
    return bool(tokens) and all(t in blob for t in tokens)


def _collect_questions(assessment: dict, critic: dict) -> list[str]:
    out: list[str] = []
    for item in assessment.get("missing_information") or []:
        q = item.get("suggested_question")
        if q:
            out.append(q)
        topic = item.get("topic")
        if topic:
            out.append(topic)
    out.extend(critic.get("missing_questions") or [])
    return out


def _infer_demo_document_type(filename: str) -> str:
    lower = filename.lower()
    if any(k in lower for k in ("policy", "process", "hr")):
        return "policy_document"
    if any(k in lower for k in ("technical", "overview")):
        return "technical_overview"
    if any(k in lower for k in ("transparency", "notice")):
        return "transparency_notice"
    if any(k in lower for k in ("pitch", "product", "brief")):
        return "product_description"
    return "general_document"
