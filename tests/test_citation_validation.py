"""Tests for assessment-time citation validation."""

from __future__ import annotations

from src.citation_validation import (
    build_evidence_index,
    validate_and_repair_assessment,
)


def _uploaded_chunk(cid: str, text: str) -> dict:
    return {
        "chunk_id": cid,
        "text": text,
        "source_type": "uploaded_document",
        "evidence_type": "uploaded_document",
    }


def _corpus_chunk(cid: str, text: str, **meta) -> dict:
    base = {
        "chunk_id": cid,
        "text": text,
        "source_type": "regulation",
        "evidence_type": "regulation",
    }
    base.update(meta)
    return base


def test_strips_corpus_from_uploaded_fact_evidence():
    uploaded = [_uploaded_chunk("sess_a_doc_chunk0", "LSTM predicts machinery failures from sensors.")]
    corpus = [_corpus_chunk(
        "corpus_EU_AI_Act_chunk100",
        "Annex III employment recruitment high-risk.",
        topic="employment_and_worker_management",
    )]
    assessment = {
        "use_case_summary": "Predictive maintenance on factory equipment.",
        "extracted_facts": {
            "purpose": {
                "value": "Predict failures",
                "confidence": "high",
                "evidence": ["corpus_EU_AI_Act_chunk100"],
            },
        },
        "preliminary_assessment": {
            "risk_tier": "minimal_risk",
            "confidence": "medium",
            "legal_citations": [],
        },
        "governance_observations": [],
        "missing_information": [],
    }
    repaired = validate_and_repair_assessment(
        assessment, uploaded_chunks=uploaded, corpus_chunks=corpus, strict_pack=True
    )
    assert repaired["extracted_facts"]["purpose"]["evidence"] == []
    assert any(r.get("action") == "corpus_cannot_support_uploaded_fact" for r in repaired["_meta"]["citation_repairs"])


def test_strips_employment_corpus_for_predictive_maintenance():
    uploaded = [_uploaded_chunk("sess_a_doc_chunk0", "Industrial predictive maintenance using LSTM sensors.")]
    corpus = [_corpus_chunk(
        "corpus_EU_AI_Act_chunk500",
        "AI for recruitment and selection of natural persons is high-risk under Annex III.",
        topic="employment_and_worker_management",
        section="Annex III",
    )]
    assessment = {
        "use_case_summary": "Industrial predictive maintenance.",
        "extracted_facts": {
            "sector": {"value": "Industrial", "confidence": "high", "evidence": ["sess_a_doc_chunk0"]},
        },
        "preliminary_assessment": {
            "risk_tier": "minimal_risk",
            "confidence": "medium",
            "reasoning": "Not high risk.",
            "legal_citations": ["corpus_EU_AI_Act_chunk500"],
        },
        "governance_observations": [],
        "missing_information": [],
    }
    repaired = validate_and_repair_assessment(
        assessment, uploaded_chunks=uploaded, corpus_chunks=corpus, strict_pack=True
    )
    assert repaired["preliminary_assessment"]["legal_citations"] == []
    actions = {r.get("action") for r in repaired["_meta"]["citation_repairs"]}
    assert "legal_topic_mismatch_for_use_case" in actions or "weak_or_unsupported_for_claim" in actions


def test_keeps_valid_uploaded_fact_citation():
    uploaded = [_uploaded_chunk("sess_a_doc_chunk0", "MachineGuard uses LSTM on vibration sensors for predictive maintenance.")]
    assessment = {
        "use_case_summary": "Predictive maintenance.",
        "extracted_facts": {
            "purpose": {
                "value": "Predictive maintenance using LSTM",
                "confidence": "high",
                "evidence": ["sess_a_doc_chunk0"],
            },
        },
        "preliminary_assessment": {"risk_tier": "minimal_risk", "legal_citations": []},
        "governance_observations": [],
        "missing_information": [],
    }
    repaired = validate_and_repair_assessment(
        assessment, uploaded_chunks=uploaded, corpus_chunks=[], strict_pack=True
    )
    assert repaired["extracted_facts"]["purpose"]["evidence"] == ["sess_a_doc_chunk0"]


def test_mock_uploaded_alias_remapped():
    uploaded = [_uploaded_chunk("sess_demo_policy_chunk0", "Rank job applicants using ML scoring.")]
    assessment = {
        "use_case_summary": "HR screening",
        "extracted_facts": {
            "purpose": {"value": "Rank applicants", "confidence": "high", "evidence": ["uploaded:chunk0"]},
        },
        "preliminary_assessment": {"risk_tier": "high_risk_candidate", "legal_citations": []},
        "governance_observations": [],
        "missing_information": [],
    }
    repaired = validate_and_repair_assessment(
        assessment, uploaded_chunks=uploaded, corpus_chunks=[], strict_pack=False
    )
    assert repaired["extracted_facts"]["purpose"]["evidence"] == ["sess_demo_policy_chunk0"]


def test_build_evidence_index():
    idx = build_evidence_index(
        [_uploaded_chunk("a", "t")],
        [_corpus_chunk("b", "t")],
    )
    assert set(idx.keys()) == {"a", "b"}
