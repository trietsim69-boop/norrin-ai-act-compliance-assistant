"""
Multi-agent orchestration: Assessment -> Critic -> (optional Revise once) -> Presenter.

Public entry point:
    run_assessment_pipeline(session_id, session_metadata=None) -> dict

Returns a single dict with:
    {
      "assessment": <final assessment dict>,
      "critic":     <final critic verdict>,
      "presented":  <display-ready dashboard data from the Presenter Agent>,
      "history":    [
        {"stage": "assessment_v1", "output": {...}},
        {"stage": "critic_v1",     "output": {...}},
        {"stage": "assessment_v2", "output": {...}},   # only if revision happened
        {"stage": "critic_v2",     "output": {...}},   # only if revision happened
        {"stage": "presenter",     "output": {...}}
      ],
      "_meta": {
        "revision_triggered": bool,
        "iterations": int
      }
    }
"""

from __future__ import annotations

from src.retrieval import retrieve_combined_context, STANDARD_QUERIES
from src.citation_resolver import resolve_citations
from src.agents.assessment_agent import assessment_agent
from src.agents.critic_agent import critic_agent
from src.agents.presenter_agent import presenter_agent

MAX_REVISIONS = 1  # MVP plan says exactly one revision pass


def run_assessment_pipeline(
    session_id: str,
    session_metadata: dict | None = None,
    top_k_per_query: int = 4,
) -> dict:
    """Run the Assessment -> Critic -> (Revise once) flow for a session."""
    session_metadata = session_metadata or {}
    history: list[dict] = []

    baseline = retrieve_combined_context(
        STANDARD_QUERIES,
        session_id=session_id,
        top_k=top_k_per_query,
    )
    uploaded_chunks = baseline["uploaded_chunks"]
    corpus_chunks = baseline["corpus_chunks"]

    assessment = assessment_agent(
        session_id=session_id,
        session_metadata=session_metadata,
        top_k_per_query=top_k_per_query,
    )
    history.append({"stage": "assessment_v1", "output": assessment})

    verdict = critic_agent(
        assessment=assessment,
        uploaded_chunks=uploaded_chunks,
        corpus_chunks=corpus_chunks,
    )
    history.append({"stage": "critic_v1", "output": verdict})

    revision_triggered = False
    if not verdict.get("pass", False) and verdict.get("revision_instruction"):
        revision_triggered = True
        revised = assessment_agent(
            session_id=session_id,
            session_metadata=session_metadata,
            top_k_per_query=top_k_per_query,
            previous_assessment=assessment,
            revision_instruction=verdict["revision_instruction"],
        )
        history.append({"stage": "assessment_v2", "output": revised})

        verdict_v2 = critic_agent(
            assessment=revised,
            uploaded_chunks=uploaded_chunks,
            corpus_chunks=corpus_chunks,
        )
        history.append({"stage": "critic_v2", "output": verdict_v2})

        assessment = revised
        verdict = verdict_v2

    chunk_lookup = resolve_citations(
        _collect_chunk_ids(assessment),
        session_id=session_id,
        evidence_cache=uploaded_chunks + corpus_chunks,
    )
    presented = presenter_agent(
        {
            "assessment": assessment,
            "critic": verdict,
            "_meta": {
                "revision_triggered": revision_triggered,
                "iterations": len(history),
            },
        },
        chunk_lookup=chunk_lookup,
    )
    history.append({"stage": "presenter", "output": presented})

    return {
        "assessment": assessment,
        "critic": verdict,
        "presented": presented,
        "history": history,
        "_meta": {
            "revision_triggered": revision_triggered,
            "iterations": len(history),
        },
    }


def _collect_chunk_ids(assessment: dict) -> list[str]:
    ids: list[str] = []
    pa = assessment.get("preliminary_assessment") or {}
    ids.extend(pa.get("legal_citations") or [])
    for fact in (assessment.get("extracted_facts") or {}).values():
        if isinstance(fact, dict):
            ids.extend(fact.get("evidence") or [])
    for obs in assessment.get("governance_observations") or []:
        ids.extend(obs.get("citations") or [])
    return [c for c in ids if c]
