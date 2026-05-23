"""
Run lightweight trigger-based checks against the demo cases.

Usage:
    python -m scripts.evaluate_triggers

The checks are intentionally simple: each demo case should activate the expected
AI Act path in mock mode and produce the expected risk direction and follow-up
signals. This is a hackathon-fit smoke test, not a legal accuracy benchmark.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

os.environ["MOCK_LLM"] = "true"

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.chunking import chunk_document
from src.pipeline import run_assessment_pipeline
from src.vector_store import add_chunks_to_uploaded, delete_session_chunks


EXPECTED_PATH = ROOT / "tests" / "expected_triggers.json"


def main() -> int:
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    failures: list[str] = []

    for case in expected:
        failures.extend(_run_case(case))

    if failures:
        print("Trigger evaluation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"Trigger evaluation passed for {len(expected)} demo cases.")
    return 0


def _run_case(case: dict) -> list[str]:
    case_name = case["case_name"]
    case_dir = ROOT / case["case_dir"]
    session_id = f"eval_{uuid.uuid4().hex[:8]}"
    failures: list[str] = []

    try:
        docs = _demo_docs(case_dir, session_id)
        chunks = []
        for doc in docs:
            chunks.extend(chunk_document(doc))

        delete_session_chunks(session_id)
        add_chunks_to_uploaded(chunks)

        result = run_assessment_pipeline(
            session_id=session_id,
            session_metadata={"case_name": case_name},
        )
        failures.extend(_assert_case(case, result))
    except Exception as exc:
        failures.append(f"{case_name}: raised {type(exc).__name__}: {exc}")
    finally:
        try:
            delete_session_chunks(session_id)
        except Exception:
            pass

    return failures


def _demo_docs(case_dir: Path, session_id: str) -> list[dict]:
    files = sorted(case_dir.glob("*.md"))
    if not files:
        raise FileNotFoundError(f"No .md files found in {case_dir}")

    return [
        {
            "filename": path.name,
            "session_id": session_id,
            "markdown_path": str(path),
            "document_type": "demo_case",
            "error": None,
        }
        for path in files
    ]


def _assert_case(case: dict, result: dict) -> list[str]:
    failures: list[str] = []
    case_name = case["case_name"]
    assessment = result.get("assessment") or {}
    pa = assessment.get("preliminary_assessment") or {}
    critic = result.get("critic") or {}

    ai_system = pa.get("ai_system")
    if ai_system != case.get("expected_ai_system"):
        failures.append(f"{case_name}: expected ai_system={case.get('expected_ai_system')}, got {ai_system}")

    risk_tier = pa.get("risk_tier")
    if risk_tier not in case.get("expected_risk_tiers", []):
        failures.append(f"{case_name}: expected risk in {case.get('expected_risk_tiers')}, got {risk_tier}")

    expected_subtype = case.get("expected_prohibited_subtype")
    if expected_subtype and pa.get("prohibited_practice_subtype") != expected_subtype:
        failures.append(
            f"{case_name}: expected prohibited subtype {expected_subtype}, "
            f"got {pa.get('prohibited_practice_subtype')}"
        )

    searchable = json.dumps(
        {
            "assessment": assessment,
            "critic": critic,
            "presented": result.get("presented") or {},
        },
        ensure_ascii=False,
    ).lower()

    for term in case.get("must_mention_terms", []):
        if term.lower() not in searchable:
            failures.append(f"{case_name}: missing expected term '{term}'")

    questions = json.dumps(
        {
            "critic_questions": critic.get("missing_questions") or [],
            "assessment_missing": assessment.get("missing_information") or [],
        },
        ensure_ascii=False,
    ).lower()
    for term in case.get("must_ask_about", []):
        if term.lower() not in questions:
            failures.append(f"{case_name}: missing follow-up topic '{term}'")

    return failures


if __name__ == "__main__":
    raise SystemExit(main())
