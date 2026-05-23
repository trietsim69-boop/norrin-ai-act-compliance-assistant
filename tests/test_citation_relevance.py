"""Unit tests for citation relevance scoring and presenter bucketing."""

from __future__ import annotations

import pytest

from src.citation_relevance import enrich_citation_row, select_claim_excerpt
from src.agents.presenter_agent import presenter_agent


def _assessment_predictive_maintenance() -> dict:
    return {
        "use_case_summary": "Industrial predictive maintenance using LSTM on sensor data.",
        "extracted_facts": {
            "purpose": {"value": "Predict machinery failures from sensor data", "confidence": "high", "evidence": []},
            "sector": {"value": "Industrial manufacturing", "confidence": "high", "evidence": []},
            "uses_gpai": {"value": "Custom LSTM model, not GPAI", "confidence": "medium", "evidence": []},
        },
        "preliminary_assessment": {
            "risk_tier": "minimal_risk",
            "confidence": "medium",
            "reasoning": "No Annex III employment category applies.",
            "legal_citations": [],
        },
    }


def _assessment_hr() -> dict:
    return {
        "use_case_summary": "HR candidate screening and shortlisting.",
        "extracted_facts": {
            "purpose": {"value": "Rank job applicants", "confidence": "high", "evidence": []},
            "sector": {"value": "Employment / HR", "confidence": "high", "evidence": []},
        },
        "preliminary_assessment": {
            "risk_tier": "high_risk_candidate",
            "confidence": "medium",
            "reasoning": "Annex III employment category may apply.",
            "legal_citations": [],
        },
    }


def _hr_annex_resolved() -> dict:
    return {
        "chunk_id": "corpus_EU_AI_Act_chunk500",
        "found": True,
        "source_type": "regulation",
        "evidence_type": "regulation",
        "section": "Annex III",
        "topic": "employment_and_worker_management",
        "law_layer": "high_risk_annex",
        "full_text": (
            "AI systems intended to be used for recruitment or selection of natural persons, "
            "notably for advertising vacancies, screening or filtering applications, "
            "and evaluating candidates during interviews shall be considered high-risk."
        ),
        "excerpt": "",
    }


def _uploaded_resolved(text: str) -> dict:
    return {
        "chunk_id": "sess_demo_policy_chunk0",
        "found": True,
        "source_type": "uploaded_document",
        "evidence_type": "uploaded_document",
        "full_text": text,
        "excerpt": "",
    }


def _corpus_resolved(text: str, **meta) -> dict:
    base = {
        "chunk_id": "corpus_EU_AI_Act_chunk100",
        "found": True,
        "source_type": "regulation",
        "evidence_type": "regulation",
        "full_text": text,
        "excerpt": "",
    }
    base.update(meta)
    return base


class TestCitationRelevance:
    def test_hr_annex_strong_for_employment_claim(self):
        row = {
            "claim": "Employment / HR high-risk area check",
            "_resolved": _hr_annex_resolved(),
        }
        enriched = enrich_citation_row(row, claim_type="legal", assessment=_assessment_hr())
        assert enriched["support_label"] in ("strong", "moderate")
        assert enriched["display_tier"] == "primary"

    def test_hr_annex_weak_for_predictive_maintenance(self):
        row = {
            "claim": "Risk classification context (regulatory reference)",
            "_resolved": _hr_annex_resolved(),
        }
        enriched = enrich_citation_row(
            row, claim_type="legal", assessment=_assessment_predictive_maintenance()
        )
        assert enriched["support_label"] in ("weak", "unsupported")
        assert enriched["display_tier"] in ("additional", "unsupported")

    def test_corpus_cannot_support_uploaded_fact(self):
        resolved = _corpus_resolved(
            "Article 6 high-risk AI systems shall comply with requirements."
        )
        row = {
            "claim": "Purpose: Predict machinery failures",
            "_resolved": resolved,
        }
        enriched = enrich_citation_row(
            row, claim_type="uploaded_fact", assessment=_assessment_predictive_maintenance()
        )
        assert enriched["support_label"] == "unsupported"
        assert "cannot support" in enriched["source_match_reason"].lower()

    def test_uploaded_cannot_support_legal_rule(self):
        resolved = _uploaded_resolved(
            "Our LSTM model monitors factory sensors for predictive maintenance."
        )
        row = {
            "claim": "Regulatory reference",
            "_resolved": resolved,
        }
        enriched = enrich_citation_row(
            row, claim_type="legal", assessment=_assessment_predictive_maintenance()
        )
        assert enriched["support_label"] == "unsupported"

    def test_custom_lstm_not_gpai(self):
        resolved = _corpus_resolved(
            "General-purpose AI models shall comply with Chapter V obligations.",
            topic="gpai",
            law_layer="gpai",
            section="Chapter V",
        )
        row = {"claim": "GPAI obligations check", "_resolved": resolved}
        enriched = enrich_citation_row(
            row, claim_type="legal", assessment=_assessment_predictive_maintenance()
        )
        assert enriched["support_label"] in ("weak", "unsupported", "moderate")

    def test_empty_overlap_excerpt_unsupported(self):
        resolved = _corpus_resolved("The weather in Brussels was pleasant yesterday.")
        row = {"claim": "Purpose: Predict machinery failures", "_resolved": resolved}
        enriched = enrich_citation_row(
            row, claim_type="uploaded_fact", assessment=_assessment_predictive_maintenance()
        )
        assert enriched["support_label"] == "unsupported"

    def test_select_claim_excerpt_finds_relevant_sentence(self):
        text = (
            "MachineGuard PM uses vibration sensors on factory pumps. "
            "The LSTM model predicts failures 48 hours ahead. "
            "Unrelated HR recruitment rules do not apply here."
        )
        excerpt, score = select_claim_excerpt(
            text, "Purpose: Predict machinery failures from sensor data"
        )
        assert "LSTM" in excerpt or "failure" in excerpt.lower()
        assert score >= 0.15

    def test_presenter_buckets(self):
        assessment = {
            "use_case_summary": "HR screening",
            "extracted_facts": {
                "purpose": {
                    "value": "Rank applicants",
                    "confidence": "high",
                    "evidence": ["sess_demo_chunk0"],
                },
            },
            "preliminary_assessment": {
                "ai_system": "yes",
                "risk_tier": "high_risk_candidate",
                "confidence": "medium",
                "reasoning": "Employment Annex III.",
                "legal_citations": ["corpus_EU_AI_Act_chunk500"],
            },
            "governance_observations": [],
            "missing_information": [],
        }
        lookup = {
            "sess_demo_chunk0": _uploaded_resolved("TalentRank ranks job applicants using ML."),
            "corpus_EU_AI_Act_chunk500": _hr_annex_resolved(),
        }
        presented = presenter_agent({"assessment": assessment, "critic": {}}, chunk_lookup=lookup)
        cit = presented["sections"]["citations"]
        for card in cit["citation_cards"]:
            assert card["support_label"] in ("strong", "moderate")
        for card in cit.get("additional_evidence") or []:
            assert card["support_label"] == "weak"
        for card in cit.get("unsupported_or_debug_evidence") or []:
            assert card["support_label"] == "unsupported"
