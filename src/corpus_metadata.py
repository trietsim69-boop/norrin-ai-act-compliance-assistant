"""
Rich metadata for EU AI Act corpus chunks and uploaded use-case documents.

Corpus chunks get law_source, law_layer, topic, citation_label, etc.
Uploaded chunks get document_type, topic (inferred), filename — not law_* fields.
"""

from __future__ import annotations

import re
from pathlib import Path

JURISDICTION_EU = "EU"

LAW_LAYER_LABELS = {
    "definitions": "Definitions",
    "core_rules": "Core rules",
    "high_risk_annex": "High-risk annex",
    "prohibited_practices": "Prohibited practices",
    "transparency": "Transparency",
    "gpai": "GPAI",
    "governance": "Governance",
    "implementation_guidance": "Implementation guidance",
}

TOPIC_LABELS = {
    "ai_system_definition": "AI system definition",
    "employment_and_worker_management": "Employment and worker management",
    "prohibited_practices": "Prohibited practices",
    "transparency_obligations": "Transparency obligations",
    "gpai_obligations": "GPAI obligations",
    "high_risk_classification": "High-risk classification",
    "human_oversight": "Human oversight",
    "risk_management": "Risk management",
    "general": "General",
    "recruitment_screening": "Recruitment screening",
    "predictive_maintenance": "Predictive maintenance",
    "manual_use_case": "Manual use-case description",
}


def infer_file_profile(stem: str) -> dict:
    """Document-level defaults from corpus filename stem."""
    stem_lower = stem.lower()

    if "prohibited" in stem_lower:
        return {
            "source_type": "official_guidance",
            "law_source": "prohibited_practices_guidance",
            "law_layer": "prohibited_practices",
            "title": "Commission Guidelines on Prohibited AI Practices",
            "jurisdiction": JURISDICTION_EU,
        }
    if "definition" in stem_lower and "system" in stem_lower:
        return {
            "source_type": "official_guidance",
            "law_source": "ai_system_definition_guidance",
            "law_layer": "definitions",
            "title": "Commission Guidelines on the Definition of an AI System",
            "jurisdiction": JURISDICTION_EU,
        }
    if "ai_act" in stem_lower or "1689" in stem_lower:
        return {
            "source_type": "regulation",
            "law_source": "eu_ai_act",
            "law_layer": "core_rules",
            "title": "EU AI Act (Regulation 2024/1689)",
            "jurisdiction": JURISDICTION_EU,
        }
    return {
        "source_type": "regulation",
        "law_source": "eu_ai_act",
        "law_layer": "core_rules",
        "title": stem.replace("_", " "),
        "jurisdiction": JURISDICTION_EU,
    }


def enrich_corpus_chunk(chunk: dict, file_profile: dict) -> dict:
    """Attach legal metadata to one corpus chunk from its text + file profile."""
    text = chunk.get("text") or ""
    section = _infer_section(text)
    article = _infer_article(text, section)
    law_layer = _infer_law_layer(text, file_profile, section)
    topic = _infer_corpus_topic(text, law_layer, file_profile)
    title = file_profile.get("title", "EU AI Act")

    citation_label = build_citation_label(
        title=title,
        section=section,
        article=article,
        law_source=file_profile.get("law_source", ""),
    )

    enriched = {
        **chunk,
        **file_profile,
        "section": section,
        "article": article,
        "law_layer": law_layer,
        "topic": topic,
        "citation_label": citation_label,
    }
    return enriched


def chroma_metadata_from_corpus_chunk(c: dict) -> dict:
    """Flatten chunk dict to Chroma-safe metadata (str/int/float/bool only)."""
    return {
        "source_type": c.get("source_type", "regulation"),
        "document_type": c.get("document_type", "eu_ai_act_corpus"),
        "filename": c.get("filename", ""),
        "title": c.get("title", ""),
        "section": c.get("section", ""),
        "article": c.get("article", ""),
        "law_source": c.get("law_source", ""),
        "law_layer": c.get("law_layer", ""),
        "topic": c.get("topic", ""),
        "jurisdiction": c.get("jurisdiction", JURISDICTION_EU),
        "citation_label": c.get("citation_label", ""),
        "chunk_index": int(c.get("chunk_index", 0)),
    }


def enrich_uploaded_chunk(chunk: dict) -> dict:
    """Attach use-case document metadata (not law_* fields)."""
    filename = chunk.get("filename", "")
    text = chunk.get("text") or ""
    doc_type = chunk.get("document_type", "general_document")
    source_type = chunk.get("source_type", "uploaded_document")

    topic = _infer_upload_topic(text, filename, doc_type, source_type)
    return {
        **chunk,
        "topic": topic,
        "jurisdiction": "",
        "citation_label": _upload_citation_label(filename, source_type, topic),
    }


def chroma_metadata_from_uploaded_chunk(c: dict) -> dict:
    meta = {
        "session_id": c.get("session_id", ""),
        "filename": c.get("filename", ""),
        "source_type": c.get("source_type", "uploaded_document"),
        "document_type": c.get("document_type", "general_document"),
        "topic": c.get("topic", ""),
        "citation_label": c.get("citation_label", ""),
        "chunk_index": int(c.get("chunk_index", 0)),
    }
    if c.get("page") is not None:
        meta["page"] = int(c["page"])
    return meta


def build_citation_label(*, title: str, section: str, article: str, law_source: str) -> str:
    short_title = title
    if law_source == "eu_ai_act":
        short_title = "EU AI Act"
    elif law_source == "ai_system_definition_guidance":
        short_title = "Commission AI System Definition Guidelines"
    elif law_source == "prohibited_practices_guidance":
        short_title = "Commission Prohibited AI Practices Guidelines"

    ref = article or section
    if ref:
        return f"{short_title} — {ref}"
    return short_title


def law_layer_display(law_layer: str) -> str:
    return LAW_LAYER_LABELS.get(law_layer, law_layer.replace("_", " ").title() if law_layer else "")


def topic_display(topic: str) -> str:
    return TOPIC_LABELS.get(topic, topic.replace("_", " ").title() if topic else "")


# ---------------------------------------------------------------------------
# Inference helpers
# ---------------------------------------------------------------------------

_SECTION_RE = re.compile(
    r"(Article\s+\d+(?:\(\d+\))?(?:\(\d+\))?|Annex\s+[IVXLC]+(?:\(\d+\))?|Chapter\s+[IVXLC]+|Recital\s+\d+)",
    re.IGNORECASE,
)
_ANNEX_POINT_RE = re.compile(
    r"Annex\s+[IVXLC]+(?:\(\d+\))?[,:\s]+(?:point\s+)?(\d+|[a-z])",
    re.IGNORECASE,
)


def _infer_section(text: str) -> str:
    match = _SECTION_RE.search(text or "")
    if not match:
        return ""
    section = match.group(1).strip()
    if section.lower().startswith("annex"):
        return section.replace("annex", "Annex").replace("ANNEX", "Annex")
    if section.lower().startswith("article"):
        return section.title().replace("Article", "Article")
    return section


def _infer_article(text: str, section: str) -> str:
    if section.lower().startswith("article"):
        return section
    lower = (text or "").lower()
    annex_point = _ANNEX_POINT_RE.search(text or "")
    if annex_point and "annex iii" in lower:
        return f"Annex III, point {annex_point.group(1)}"
    if section.lower().startswith("annex"):
        if "area 4" in lower or "point 4" in lower or "employment" in lower[:400]:
            return "Annex III, point 4"
        return section
    return ""


def _infer_law_layer(text: str, file_profile: dict, section: str) -> str:
    lower = (text or "").lower()
    sec_lower = section.lower()

    if file_profile.get("law_source") == "prohibited_practices_guidance":
        return "prohibited_practices"
    if file_profile.get("law_source") == "ai_system_definition_guidance":
        return "definitions"

    if "article 5" in sec_lower or re.search(r"\barticle\s+5\b", lower):
        return "prohibited_practices"
    if "annex iii" in sec_lower or "annex iii" in lower:
        return "high_risk_annex"
    if "article 50" in sec_lower or "transparency" in lower[:300]:
        return "transparency"
    if "article 3" in sec_lower or re.search(r"\barticle\s+3\b", lower):
        return "definitions"
    if "chapter v" in sec_lower or "general-purpose" in lower or "general purpose" in lower:
        return "gpai"
    if any(k in lower for k in ("annex iv", "technical documentation", "risk management system")):
        return "governance"
    if "article 6" in sec_lower:
        return "high_risk_annex"

    return file_profile.get("law_layer", "core_rules")


def _infer_corpus_topic(text: str, law_layer: str, file_profile: dict) -> str:
    lower = (text or "").lower()

    if law_layer == "definitions" or file_profile.get("law_source") == "ai_system_definition_guidance":
        return "ai_system_definition"
    if law_layer == "prohibited_practices":
        return "prohibited_practices"
    if law_layer == "transparency":
        return "transparency_obligations"
    if law_layer == "gpai":
        return "gpai_obligations"
    if any(k in lower for k in ("employment", "recruit", "worker management", "job applicant", "hiring")):
        return "employment_and_worker_management"
    if "high-risk" in lower or "high risk" in lower or law_layer == "high_risk_annex":
        return "high_risk_classification"
    if "human oversight" in lower or "article 14" in lower:
        return "human_oversight"
    if "risk management" in lower or "article 9" in lower:
        return "risk_management"
    return "general"


def _infer_upload_topic(text: str, filename: str, document_type: str, source_type: str) -> str:
    blob = f"{filename} {document_type} {text}".lower()
    if source_type == "user_input":
        return "manual_use_case"
    if any(k in blob for k in ("recruit", "hiring", "candidate", "cv", "applicant")):
        return "recruitment_screening"
    if any(k in blob for k in ("maintenance", "machinery", "sensor", "predictive", "engine")):
        return "predictive_maintenance"
    if "hr" in document_type or "hr" in blob:
        return "recruitment_screening"
    return "general"


def _upload_citation_label(filename: str, source_type: str, topic: str) -> str:
    if source_type == "user_input":
        return "Manual use-case description"
    stem = Path(filename).stem if filename else "Uploaded document"
    pretty = stem.replace("-", " ").replace("_", " ").title()
    return pretty or "Uploaded document"


def infer_retrieval_targets(uploaded_chunks: list[dict]) -> list[dict]:
    """
    From uploaded/user evidence, derive targeted corpus queries with metadata filters.
    Returns list of {query, where} dicts for Chroma.
    """
    if not uploaded_chunks:
        return []

    blob = " ".join(c.get("text", "") for c in uploaded_chunks).lower()
    topics = {c.get("topic", "") for c in uploaded_chunks}
    targets: list[dict] = []

    def add(query: str, where: dict) -> None:
        for t in targets:
            if t["query"] == query and t["where"] == where:
                return
        targets.append({"query": query, "where": where})

    # Always anchor classification with definition + core high-risk paths
    add(
        "Does this system meet the EU AI Act definition of an AI system?",
        {"law_layer": "definitions"},
    )

    if any(k in blob for k in ("recruit", "hiring", "candidate", "employment", "worker", "hr", "applicant")):
        add(
            "Annex III employment worker management recruitment hiring",
            {"law_layer": "high_risk_annex"},
        )
    if "recruitment_screening" in topics or "employment_and_worker_management" in topics:
        add(
            "high-risk AI in employment and recruitment Annex III",
            {"topic": "employment_and_worker_management"},
        )

    if any(k in blob for k in ("chatbot", "conversational", "customer support", "virtual assistant")):
        add(
            "transparency obligations chatbot AI interaction Article 50",
            {"law_layer": "transparency"},
        )

    if any(k in blob for k in ("emotion", "facial", "biometric", "affect", "mood")):
        add(
            "prohibited emotion recognition workplace Article 5",
            {"law_layer": "prohibited_practices"},
        )

    if any(k in blob for k in ("gpt", "llm", "large language model", "general purpose", "claude", "openai")):
        add(
            "general purpose AI model GPAI provider deployer obligations",
            {"law_layer": "gpai"},
        )

    if any(k in blob for k in ("maintenance", "machinery", "safety component", "industrial")):
        add(
            "high-risk safety components machinery product Annex III",
            {"law_layer": "high_risk_annex"},
        )

    return targets
