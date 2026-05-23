"""
Assessment Agent — produces a structured first-pass EU AI Act assessment.

Architecture: hybrid ReAct
    1. Receive baseline evidence from the pipeline, or retrieve it directly
       when the agent is run standalone.
    2. Single main LLM call that returns structured JSON. The LLM can request
       additional retrievals via the "needs_more_evidence" field.
    3. If extra evidence is requested, run those queries and call the LLM once
       more with the enlarged evidence pack. Capped at MAX_REACT_ITERATIONS.

Mock mode: when MOCK_LLM=true (src.config), the agent returns one of five
pre-canned fixtures keyed to keyword signals in the retrieved chunks. Lets
you run the whole pipeline end-to-end without spending an API credit.
"""

from __future__ import annotations

import json
from typing import Any

from src.llm import call_llm
from src.retrieval import (
    retrieve_combined_context,
    retrieve_uploaded_context,
    retrieve_ai_act_context,
    STANDARD_QUERIES,
)

MAX_REACT_ITERATIONS = 2
MAX_EXTRA_QUERIES_PER_ITER = 3


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

ASSESSMENT_SYSTEM_PROMPT = """You are the Assessment Agent in a multi-agent EU AI Act compliance review system.

Your job: produce a structured, evidence-grounded preliminary assessment of an AI use case based on (a) excerpts from uploaded user documents and (b) excerpts from the EU AI Act and Commission guidelines.

CRITICAL RULES
1. You only know what is in the provided evidence chunks. Do not invent facts. If something is unclear or absent, flag it under missing_information.
2. Every major claim must cite the chunk_id(s) of supporting evidence. Use uploaded chunk_ids for factual claims and corpus chunk_ids for legal claims.
3. Never present a regulatory claim without a corpus citation.
4. Avoid sounding like final legal advice. Use qualified language: "appears to", "likely", "may fall within".
5. Lower confidence to "low" when key facts (purpose, oversight, decision impact, deployment context, GPAI use) are missing.

LEGAL SCOPE YOU MUST CHECK
- Article 3 AI system definition: machine-based system, designed to operate with varying levels of autonomy, may exhibit adaptiveness after deployment, explicit or implicit objectives, input received, inference from input, and generated outputs such as predictions, content, recommendations, or decisions that can influence physical or virtual environments.
- Definition guideline exclusions: basic data processing, classical heuristics/rules with no meaningful inference, simple prediction systems that do not infer beyond conventional processing, and mathematical optimization. If an exclusion may apply, set ai_system to "no" or "unclear" and explain it.
- Article 5 prohibited practices: 5(1)(a) manipulation/deception, 5(1)(b) exploitation of vulnerabilities, 5(1)(c) social scoring, 5(1)(d) crime prediction, 5(1)(e) untargeted facial-image scraping, 5(1)(f) workplace/education emotion recognition, 5(1)(g) biometric categorisation of sensitive attributes, 5(1)(h) real-time remote biometric identification in public spaces for law enforcement.
- Article 6 and Annex III high-risk areas: biometrics; critical infrastructure; education/vocational training; employment/worker management; essential private/public services and benefits; law enforcement; migration/asylum/border control; administration of justice and democratic processes.
- Article 50 transparency and labelling: chatbots, AI interaction disclosure, AI-generated/synthetic content, and deepfakes.
- Chapter V GPAI: identify whether the organization appears to be a provider or deployer of a GPAI model and what documentation or responsibility-chain questions remain.

YOUR AUTONOMOUS DECISIONS
- Which uploaded facts are relevant to an AI Act analysis (ignore boilerplate).
- Whether the system meets the AI Act definition of an AI system (Article 3).
- Which risk path applies: prohibited / high-risk / limited / minimal / GPAI / unclear.
- Whether GPAI or transparency obligations apply.
- What governance observations are proportional to the detected risk tier.
- What is missing and what follow-up question would resolve it.
- Whether you need more evidence on a specific point — request it via "needs_more_evidence".

OUTPUT — a single valid JSON object with EXACTLY this shape (no extra keys, no prose outside JSON):

{
  "use_case_summary": "1-3 sentences describing what the AI system does",
  "extracted_facts": {
    "purpose":         {"value": "...", "confidence": "low|medium|high", "evidence": ["chunk_id"]},
    "affected_persons":{"value": "...", "confidence": "low|medium|high", "evidence": ["chunk_id"]},
    "sector":          {"value": "...", "confidence": "low|medium|high", "evidence": ["chunk_id"]},
    "automation_level":{"value": "...", "confidence": "low|medium|high", "evidence": ["chunk_id"]},
    "human_oversight": {"value": "...", "confidence": "low|medium|high", "evidence": ["chunk_id"]},
    "uses_gpai":       {"value": "...", "confidence": "low|medium|high", "evidence": ["chunk_id"]}
  },
  "preliminary_assessment": {
    "ai_system": "yes|no|unclear",
    "ai_system_reasoning": "why",
    "ai_system_definition_notes": "brief element-by-element Article 3 analysis, including inference and autonomy",
    "definition_exclusion": "none|basic_data_processing|classical_heuristics|simple_prediction|mathematical_optimization|unclear",
    "risk_tier": "prohibited|high_risk_candidate|limited_risk|minimal_risk|gpai_obligations|unclear",
    "prohibited_practice_subtype": "none|5(1)(a)_manipulation_deception|5(1)(b)_vulnerability_exploitation|5(1)(c)_social_scoring|5(1)(d)_crime_prediction|5(1)(e)_facial_image_scraping|5(1)(f)_workplace_education_emotion_recognition|5(1)(g)_sensitive_biometric_categorisation|5(1)(h)_real_time_remote_biometric_identification|unclear",
    "high_risk_domain": "none|Annex III area 1 biometrics|Annex III area 2 critical infrastructure|Annex III area 3 education and vocational training|Annex III area 4 employment and worker management|Annex III area 5 essential services|Annex III area 6 law enforcement|Annex III area 7 migration/asylum/border control|Annex III area 8 justice and democratic processes|unclear",
    "transparency_or_gpai_notes": "brief notes on Article 50 and/or GPAI relevance, or 'none identified'",
    "confidence": "low|medium|high",
    "reasoning": "1-3 paragraphs explaining the classification with citations",
    "legal_citations": ["corpus_chunk_id"]
  },
  "governance_observations": [
    {"area": "documentation|risk_management|transparency|human_oversight|monitoring|accountability|role_clarity",
     "observation": "...",
     "citations": ["chunk_id"]}
  ],
  "missing_information": [
    {"topic": "...", "why_it_matters": "...", "suggested_question": "..."}
  ],
  "needs_more_evidence": []
}

Set "needs_more_evidence" to [] when you have what you need. Otherwise, list up to 3 short, specific search queries (natural language) to retrieve more chunks.
"""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def assessment_agent(
    session_id: str,
    session_metadata: dict | None = None,
    queries: list[str] | None = None,
    top_k_per_query: int = 4,
    uploaded_chunks: list[dict] | None = None,
    corpus_chunks: list[dict] | None = None,
    *,
    previous_assessment: dict | None = None,
    revision_instruction: str | None = None,
) -> dict:
    """
    Run the assessment pipeline for a session. Returns the final structured assessment.

    The returned dict has the shape declared in ASSESSMENT_SYSTEM_PROMPT plus a
    "_meta" key with debug info (iterations, total evidence chunks used).

    Revision mode:
        If `previous_assessment` and `revision_instruction` are provided, the agent
        receives them as additional context and the LLM is asked to revise the
        previous output according to the critic's instruction. Also returns the
        revised result in the same shape.
    """
    session_metadata = session_metadata or {}
    is_revision = previous_assessment is not None and revision_instruction is not None

    if uploaded_chunks is None or corpus_chunks is None:
        baseline = retrieve_combined_context(
            queries or STANDARD_QUERIES,
            session_id=session_id,
            top_k=top_k_per_query,
        )
        if uploaded_chunks is None:
            uploaded_chunks = baseline["uploaded_chunks"]
        if corpus_chunks is None:
            corpus_chunks = baseline["corpus_chunks"]

    extra_chunks: list[dict] = []
    iterations = 0
    last_response: dict[str, Any] = {}

    while True:
        user_msg = _build_user_message(
            session_metadata=session_metadata,
            uploaded_chunks=uploaded_chunks,
            corpus_chunks=corpus_chunks,
            extra_chunks=extra_chunks,
            previous_assessment=previous_assessment if is_revision else None,
            revision_instruction=revision_instruction if is_revision else None,
        )

        raw = call_llm(
            messages=[
                {"role": "system", "content": ASSESSMENT_SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
            response_format="json",
            temperature=0.2,
            max_tokens=3500,
            mock=_pick_mock_fixture(
                uploaded_chunks,
                corpus_chunks,
                revision_instruction=revision_instruction,
            ),
        )

        last_response = _safe_json_loads(raw["content"])
        iterations += 1

        needs_more = last_response.get("needs_more_evidence") or []
        if not needs_more or iterations >= MAX_REACT_ITERATIONS:
            break

        for q in needs_more[:MAX_EXTRA_QUERIES_PER_ITER]:
            extra_chunks.extend(retrieve_uploaded_context(q, session_id=session_id, top_k=top_k_per_query))
            extra_chunks.extend(retrieve_ai_act_context(q, top_k=top_k_per_query))
        extra_chunks = _dedupe_chunks(extra_chunks)

    uploaded_evidence_ids = _chunk_ids_by_source([*uploaded_chunks, *extra_chunks], "uploaded")
    corpus_evidence_ids = _chunk_ids_by_source([*corpus_chunks, *extra_chunks], "corpus")
    last_response["_meta"] = {
        "iterations": iterations,
        "uploaded_chunks_used": len(uploaded_chunks),
        "corpus_chunks_used": len(corpus_chunks),
        "extra_chunks_used": len(extra_chunks),
        "uploaded_chunk_ids_available": uploaded_evidence_ids,
        "corpus_chunk_ids_available": corpus_evidence_ids,
        "was_revision": is_revision,
    }
    return last_response


# ---------------------------------------------------------------------------
# Prompt construction helpers
# ---------------------------------------------------------------------------

def _build_user_message(
    *,
    session_metadata: dict,
    uploaded_chunks: list[dict],
    corpus_chunks: list[dict],
    extra_chunks: list[dict],
    previous_assessment: dict | None = None,
    revision_instruction: str | None = None,
) -> str:
    parts: list[str] = []

    if session_metadata:
        parts.append("## Session metadata")
        parts.append(json.dumps(session_metadata, indent=2, ensure_ascii=False))

    parts.append("## Uploaded document evidence")
    parts.append(_format_chunks(uploaded_chunks) or "(none retrieved)")

    parts.append("## EU AI Act corpus evidence")
    parts.append(_format_chunks(corpus_chunks) or "(none retrieved)")

    if extra_chunks:
        parts.append("## Additional evidence retrieved on request")
        parts.append(_format_chunks(extra_chunks))

    if previous_assessment and revision_instruction:
        parts.append("## Previous assessment")
        parts.append(json.dumps(previous_assessment, indent=2, ensure_ascii=False))
        parts.append("## Critic revision instruction")
        parts.append(revision_instruction)
        parts.append(
            "## Instructions\n"
            "Revise the previous assessment to address the critic's instruction. "
            "Re-emit the FULL JSON object in the same shape. Keep what is correct, "
            "fix what the critic flagged, and lower confidence levels if appropriate."
        )
    else:
        parts.append(
            "## Instructions\n"
            "Produce the JSON assessment described in the system prompt. "
            "Cite chunk_ids exactly as they appear above. "
            "If anything important is missing, list it under missing_information "
            "and (optionally) request up to 3 more targeted retrievals via "
            "needs_more_evidence."
        )
    return "\n\n".join(parts)


def _format_chunks(chunks: list[dict], max_text_chars: int = 800) -> str:
    if not chunks:
        return ""
    lines: list[str] = []
    for c in chunks:
        text = c.get("text", "")
        if len(text) > max_text_chars:
            text = text[:max_text_chars].rstrip() + " […]"
        header_bits = [c.get("chunk_id", "?")]
        if c.get("filename"):
            header_bits.append(f"file={c['filename']}")
        if c.get("section"):
            header_bits.append(f"section={c['section']}")
        if c.get("source_type"):
            header_bits.append(f"type={c['source_type']}")
        lines.append(f"[{' | '.join(header_bits)}]\n{text}")
    return "\n\n---\n\n".join(lines)


def _dedupe_chunks(chunks: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for c in chunks:
        cid = c.get("chunk_id", "")
        if cid and cid not in seen:
            seen.add(cid)
            out.append(c)
    return out


def _chunk_ids_by_source(chunks: list[dict], evidence_source: str) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for c in chunks:
        cid = c.get("chunk_id", "")
        if not cid or cid in seen:
            continue
        source = c.get("evidence_source")
        source_type = c.get("source_type", "")
        if evidence_source == "uploaded":
            matches = source == "uploaded" or source_type == "uploaded_document"
        else:
            matches = source == "corpus" or source_type in {"regulation", "official_guidance"}
        if matches:
            seen.add(cid)
            ids.append(cid)
    return ids


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

def _pick_mock_fixture(
    uploaded_chunks: list[dict],
    corpus_chunks: list[dict],
    *,
    revision_instruction: str | None = None,
) -> dict:
    """Detect which demo case the uploaded chunks resemble and return its fixture.
    When a revision instruction is present, return a lightly-revised version
    of the fixture (lower confidence + a note acknowledging the critic)."""
    blob = " ".join(c.get("text", "") for c in uploaded_chunks).lower()

    def has(*words: str) -> bool:
        return any(w in blob for w in words)

    if has("emotion", "mood", "affect") and has("workplace", "employee", "worker"):
        base = _MOCK_EMOTION
    elif has("recruit", "candidate", "hiring", "applicant", "screening", "talentrank"):
        base = _MOCK_HR
    elif has("spam", "filter") and not has("recruit"):
        base = _MOCK_SPAM
    elif has("chatbot", "conversational", "virtual assistant", "customer support"):
        base = _MOCK_CHATBOT
    elif has("gpt", "llm", "large language model", "claude", "report generator"):
        base = _MOCK_GPAI
    else:
        base = _MOCK_GENERIC

    revised = _materialise_fixture(base, uploaded_chunks, corpus_chunks)
    if "preliminary_assessment" in revised:
        revised["preliminary_assessment"].setdefault("ai_system_definition_notes", "")
        revised["preliminary_assessment"].setdefault("definition_exclusion", "none")
        revised["preliminary_assessment"].setdefault("prohibited_practice_subtype", "none")
        revised["preliminary_assessment"].setdefault("high_risk_domain", "none")
        revised["preliminary_assessment"].setdefault("transparency_or_gpai_notes", "none identified")

    if revision_instruction is None:
        return {"content": json.dumps(revised, ensure_ascii=False), "tool_calls": None}

    if "preliminary_assessment" in revised:
        revised["preliminary_assessment"]["confidence"] = "low"
        revised["preliminary_assessment"]["reasoning"] = (
            "[Revised after critic review] " + revised["preliminary_assessment"].get("reasoning", "")
        )
    revised["needs_more_evidence"] = []
    return {"content": json.dumps(revised, ensure_ascii=False), "tool_calls": None}


def _materialise_fixture(
    fixture: dict,
    uploaded_chunks: list[dict],
    corpus_chunks: list[dict],
) -> dict:
    data = json.loads(fixture["content"])
    uploaded_ids = [c.get("chunk_id", "") for c in uploaded_chunks if c.get("chunk_id")]

    corpus_mapping = {
        "corpus:annex_iii_area_4": _best_corpus_id(corpus_chunks, ["annex iii", "employment", "recruitment", "worker"]),
        "corpus:article_6": _best_corpus_id(corpus_chunks, ["article 6", "high-risk", "annex iii"]),
        "corpus:article_14": _best_corpus_id(corpus_chunks, ["article 14", "human oversight"]),
        "corpus:article_11": _best_corpus_id(corpus_chunks, ["article 11", "technical documentation"]),
        "corpus:article_9": _best_corpus_id(corpus_chunks, ["article 9", "risk management"]),
        "corpus:article_50": _best_corpus_id(corpus_chunks, ["article 50", "transparency", "chatbot", "deep fake", "ai-generated"]),
        "corpus:chapter_v_gpai": _best_corpus_id(corpus_chunks, ["chapter v", "general-purpose", "gpai"]),
        "corpus:chapter_iii": _best_corpus_id(corpus_chunks, ["provider", "deployer", "chapter iii"]),
        "corpus:article_5_1_f": _best_corpus_id(corpus_chunks, ["article 5", "emotion recognition", "workplace", "educational"]),
        "corpus:prohibited_practices_guidance": _best_corpus_id(corpus_chunks, ["prohibited", "emotion recognition", "workplace"]),
        "corpus:article_53": _best_corpus_id(corpus_chunks, ["article 53", "general-purpose", "gpai"]),
        "corpus:annex_iii": _best_corpus_id(corpus_chunks, ["annex iii"]),
    }

    def replace(value: Any) -> Any:
        if isinstance(value, str):
            if value.startswith("uploaded:chunk"):
                try:
                    idx = int(value.rsplit("chunk", 1)[1])
                except ValueError:
                    idx = 0
                if uploaded_ids:
                    return uploaded_ids[min(idx, len(uploaded_ids) - 1)]
            if value in corpus_mapping and corpus_mapping[value]:
                return corpus_mapping[value]
            return value
        if isinstance(value, list):
            return [replace(v) for v in value]
        if isinstance(value, dict):
            return {k: replace(v) for k, v in value.items()}
        return value

    return replace(data)


def _best_corpus_id(corpus_chunks: list[dict], keywords: list[str]) -> str:
    best_id = ""
    best_score = -1
    for c in corpus_chunks:
        cid = c.get("chunk_id", "")
        text = f"{c.get('text', '')} {c.get('section', '')} {c.get('title', '')}".lower()
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score and cid:
            best_id = cid
            best_score = score
    if best_score <= 0 and corpus_chunks:
        return corpus_chunks[0].get("chunk_id", "")
    return best_id


def _fixture(d: dict) -> dict:
    return {"content": json.dumps(d, ensure_ascii=False), "tool_calls": None}


_MOCK_HR = _fixture({
    "use_case_summary": "An AI-powered recruitment tool that scores and ranks job candidates from CVs and structured questionnaires, producing a shortlist for human recruiters.",
    "extracted_facts": {
        "purpose":          {"value": "Rank job applicants and produce a shortlist", "confidence": "high", "evidence": ["uploaded:chunk0"]},
        "affected_persons": {"value": "Job applicants",                              "confidence": "high", "evidence": ["uploaded:chunk0"]},
        "sector":           {"value": "Employment / HR",                             "confidence": "high", "evidence": ["uploaded:chunk0"]},
        "automation_level": {"value": "Recommends shortlist; recruiter approves",    "confidence": "medium", "evidence": ["uploaded:chunk1"]},
        "human_oversight":  {"value": "Recruiter reviews top 20 candidates",         "confidence": "medium", "evidence": ["uploaded:chunk1"]},
        "uses_gpai":        {"value": "Uses an LLM for CV field extraction",         "confidence": "medium", "evidence": ["uploaded:chunk1"]}
    },
    "preliminary_assessment": {
        "ai_system": "yes",
        "ai_system_reasoning": "Uses a trained ML model and an LLM to infer outputs (Article 3).",
        "ai_system_definition_notes": "Machine-based models infer candidate scores and extracted CV fields from input documents for the objective of recruitment shortlisting.",
        "definition_exclusion": "none",
        "risk_tier": "high_risk_candidate",
        "prohibited_practice_subtype": "none",
        "high_risk_domain": "Annex III area 4 employment and worker management",
        "transparency_or_gpai_notes": "GPAI may be relevant because an LLM is used for CV field extraction.",
        "confidence": "medium",
        "reasoning": "The system is used in recruitment/selection of natural persons, which is explicitly listed under Annex III area 4 (employment, workers management). It therefore appears to fall within the high-risk category of Article 6(2). Even though a human recruiter approves the final shortlist, the AI strongly shapes which candidates are seen, so the Annex III(2) exclusion is unlikely to apply.",
        "legal_citations": ["corpus:annex_iii_area_4", "corpus:article_6"]
    },
    "governance_observations": [
        {"area": "human_oversight",   "observation": "Document a clear oversight protocol — what the recruiter can override and how.", "citations": ["corpus:article_14"]},
        {"area": "documentation",     "observation": "Maintain technical documentation per Annex IV.",                                   "citations": ["corpus:article_11"]},
        {"area": "risk_management",   "observation": "Implement a risk management system for the ML and LLM components.",               "citations": ["corpus:article_9"]}
    ],
    "missing_information": [
        {"topic": "Final decision impact", "why_it_matters": "Affects whether the Annex III(2) exclusion applies.", "suggested_question": "Can a candidate be rejected without a recruiter review?"},
        {"topic": "Provider vs deployer role", "why_it_matters": "Different obligations apply.",                    "suggested_question": "Does your organisation develop the model or only deploy it?"}
    ],
    "needs_more_evidence": []
})

_MOCK_CHATBOT = _fixture({
    "use_case_summary": "A customer support chatbot that interacts with end users via natural language, likely built on top of a third-party LLM.",
    "extracted_facts": {
        "purpose":          {"value": "Answer customer support questions",     "confidence": "high",   "evidence": ["uploaded:chunk0"]},
        "affected_persons": {"value": "Customers / end users",                  "confidence": "high",   "evidence": ["uploaded:chunk0"]},
        "sector":           {"value": "Customer service",                      "confidence": "medium", "evidence": ["uploaded:chunk0"]},
        "automation_level": {"value": "Fully automated responses",             "confidence": "medium", "evidence": ["uploaded:chunk1"]},
        "human_oversight":  {"value": "Unclear — no explicit human handoff",   "confidence": "low",    "evidence": []},
        "uses_gpai":        {"value": "Likely — uses a third-party LLM",       "confidence": "medium", "evidence": ["uploaded:chunk1"]}
    },
    "preliminary_assessment": {
        "ai_system": "yes",
        "ai_system_reasoning": "Generates natural-language responses through LLM inference (Article 3).",
        "ai_system_definition_notes": "The chatbot infers natural-language responses from user prompts and support context with a human-facing interaction objective.",
        "definition_exclusion": "none",
        "risk_tier": "limited_risk",
        "prohibited_practice_subtype": "none",
        "high_risk_domain": "none",
        "transparency_or_gpai_notes": "Article 50 chatbot disclosure is relevant; GPAI responsibility-chain questions remain if a third-party LLM is used.",
        "confidence": "medium",
        "reasoning": "The system interacts directly with natural persons. Article 50(1) requires that users are informed they are interacting with an AI. If a third-party GPAI model is used, deployer obligations under Chapter V are also engaged.",
        "legal_citations": ["corpus:article_50", "corpus:chapter_v_gpai"]
    },
    "governance_observations": [
        {"area": "transparency",   "observation": "Disclose to users that they are interacting with an AI.", "citations": ["corpus:article_50"]},
        {"area": "role_clarity",   "observation": "Confirm whether you are provider, deployer, or both.",   "citations": ["corpus:chapter_iii"]}
    ],
    "missing_information": [
        {"topic": "GPAI model identity",    "why_it_matters": "Determines deployer obligations under Chapter V.", "suggested_question": "Which third-party LLM provider is used?"},
        {"topic": "Human escalation path", "why_it_matters": "Affects user protection.",                         "suggested_question": "Can users escalate to a human agent?"}
    ],
    "needs_more_evidence": []
})

_MOCK_EMOTION = _fixture({
    "use_case_summary": "A workplace analytics tool that infers employees' emotional or mood states from facial expressions or voice patterns.",
    "extracted_facts": {
        "purpose":          {"value": "Infer employee emotional state",            "confidence": "high",   "evidence": ["uploaded:chunk0"]},
        "affected_persons": {"value": "Employees / workers",                       "confidence": "high",   "evidence": ["uploaded:chunk0"]},
        "sector":           {"value": "Workplace / HR analytics",                  "confidence": "high",   "evidence": ["uploaded:chunk0"]},
        "automation_level": {"value": "Real-time inference",                       "confidence": "medium", "evidence": ["uploaded:chunk1"]},
        "human_oversight":  {"value": "Unclear",                                   "confidence": "low",    "evidence": []},
        "uses_gpai":        {"value": "Not indicated",                             "confidence": "low",    "evidence": []}
    },
    "preliminary_assessment": {
        "ai_system": "yes",
        "ai_system_reasoning": "Infers emotional state from biometric/behavioural input (Article 3).",
        "ai_system_definition_notes": "The system infers mood or emotional state from facial or voice signals, which goes beyond simple data processing.",
        "definition_exclusion": "none",
        "risk_tier": "prohibited",
        "prohibited_practice_subtype": "5(1)(f)_workplace_education_emotion_recognition",
        "high_risk_domain": "none",
        "transparency_or_gpai_notes": "No separate Article 50 or GPAI path is evident from the uploaded facts.",
        "confidence": "medium",
        "reasoning": "The evidence is consistent with an emotion-recognition system used in a workplace context. Article 5(1)(f) prohibits emotion recognition in workplaces and educational institutions, with narrow exceptions for medical and safety purposes. The system appears to fall within Article 5(1)(f) unless a medical or safety exception applies. This requires legal review before deployment.",
        "legal_citations": ["corpus:article_5_1_f", "corpus:prohibited_practices_guidance"]
    },
    "governance_observations": [
        {"area": "accountability", "observation": "Halt deployment pending legal review of Article 5(1)(f) applicability.", "citations": ["corpus:article_5_1_f"]},
        {"area": "documentation",  "observation": "Document precisely what is inferred and from what signals.",             "citations": []}
    ],
    "missing_information": [
        {"topic": "What is inferred",         "why_it_matters": "Determines if Article 5(1)(f) applies.",          "suggested_question": "Does the system infer emotions, or only physical states like attentiveness?"},
        {"topic": "Medical or safety exception", "why_it_matters": "Only exception to Article 5(1)(f).",            "suggested_question": "Is the use specifically for a medical or safety purpose?"}
    ],
    "needs_more_evidence": []
})

_MOCK_SPAM = _fixture({
    "use_case_summary": "An email spam filter that classifies incoming messages as spam or legitimate.",
    "extracted_facts": {
        "purpose":          {"value": "Filter spam emails",                    "confidence": "high",   "evidence": ["uploaded:chunk0"]},
        "affected_persons": {"value": "Email recipients",                      "confidence": "medium", "evidence": ["uploaded:chunk0"]},
        "sector":           {"value": "Email infrastructure",                  "confidence": "medium", "evidence": ["uploaded:chunk0"]},
        "automation_level": {"value": "Fully automated",                       "confidence": "medium", "evidence": ["uploaded:chunk0"]},
        "human_oversight":  {"value": "User can mark messages as not-spam",    "confidence": "medium", "evidence": ["uploaded:chunk1"]},
        "uses_gpai":        {"value": "No",                                    "confidence": "high",   "evidence": ["uploaded:chunk1"]}
    },
    "preliminary_assessment": {
        "ai_system": "yes",
        "ai_system_reasoning": "Uses an ML classifier to infer spam/not-spam labels (Article 3).",
        "ai_system_definition_notes": "The described ML classifier infers message labels from email content; if it were only fixed rules, the definition exclusion would need reassessment.",
        "definition_exclusion": "none",
        "risk_tier": "minimal_risk",
        "prohibited_practice_subtype": "none",
        "high_risk_domain": "none",
        "transparency_or_gpai_notes": "No chatbot, deepfake, AI-generated content labelling, or GPAI path is indicated.",
        "confidence": "high",
        "reasoning": "Spam filtering is a narrow procedural task with limited impact on individuals. It does not fall under Annex III and is not a prohibited practice. The AI Act imposes no mandatory requirements beyond general good practice for minimal-risk systems.",
        "legal_citations": ["corpus:article_6", "corpus:annex_iii"]
    },
    "governance_observations": [
        {"area": "monitoring",   "observation": "Monitor false-positive rates to avoid blocking legitimate mail.", "citations": []},
        {"area": "transparency", "observation": "Give users a way to retrieve and unmark filtered messages.",      "citations": []}
    ],
    "missing_information": [],
    "needs_more_evidence": []
})

_MOCK_GPAI = _fixture({
    "use_case_summary": "An internal tool that uses a third-party GPAI model (e.g. GPT) to generate business reports from structured data.",
    "extracted_facts": {
        "purpose":          {"value": "Generate internal reports using a GPAI model", "confidence": "high",   "evidence": ["uploaded:chunk0"]},
        "affected_persons": {"value": "Internal employees who read the reports",      "confidence": "medium", "evidence": ["uploaded:chunk0"]},
        "sector":           {"value": "Internal business operations",                 "confidence": "medium", "evidence": ["uploaded:chunk0"]},
        "automation_level": {"value": "Report draft generated automatically",         "confidence": "medium", "evidence": ["uploaded:chunk1"]},
        "human_oversight":  {"value": "Reports reviewed by an analyst before use",    "confidence": "medium", "evidence": ["uploaded:chunk1"]},
        "uses_gpai":        {"value": "Yes — third-party LLM via API",                "confidence": "high",   "evidence": ["uploaded:chunk1"]}
    },
    "preliminary_assessment": {
        "ai_system": "yes",
        "ai_system_reasoning": "Uses a GPAI model to generate natural-language output (Article 3).",
        "ai_system_definition_notes": "A GPAI model infers generated report text from structured input data and user instructions.",
        "definition_exclusion": "none",
        "risk_tier": "gpai_obligations",
        "prohibited_practice_subtype": "none",
        "high_risk_domain": "unclear",
        "transparency_or_gpai_notes": "Chapter V provider obligations sit primarily with the GPAI provider, while deployer responsibilities and downstream high-risk use remain to be checked.",
        "confidence": "medium",
        "reasoning": "The organisation is a deployer of a third-party GPAI model. Provider obligations under Article 53 sit with the model vendor; the deployer carries operational obligations under Chapter III (human oversight, transparency, appropriate use). If the generated reports inform decisions in a high-risk area (e.g. HR, credit), high-risk obligations may also apply.",
        "legal_citations": ["corpus:chapter_v_gpai", "corpus:article_53", "corpus:chapter_iii"]
    },
    "governance_observations": [
        {"area": "role_clarity",      "observation": "Confirm deployer role and obtain Article 53 documentation from the GPAI provider.", "citations": ["corpus:article_53"]},
        {"area": "human_oversight",   "observation": "Maintain mandatory analyst review of every generated report before use.",          "citations": ["corpus:article_14"]},
        {"area": "transparency",      "observation": "Mark or label AI-generated content where required (Article 50(2)–(3)).",           "citations": ["corpus:article_50"]}
    ],
    "missing_information": [
        {"topic": "Provider documentation", "why_it_matters": "Required for compliant deployment.",          "suggested_question": "Has the GPAI provider supplied Article 53 documentation?"},
        {"topic": "Downstream use of reports", "why_it_matters": "May trigger high-risk obligations.",       "suggested_question": "Are the reports used to inform HR, credit, or other high-risk decisions?"}
    ],
    "needs_more_evidence": []
})

_MOCK_GENERIC = _fixture({
    "use_case_summary": "An AI system whose purpose could not be confidently determined from the uploaded evidence.",
    "extracted_facts": {
        "purpose":          {"value": "Unclear", "confidence": "low", "evidence": []},
        "affected_persons": {"value": "Unclear", "confidence": "low", "evidence": []},
        "sector":           {"value": "Unclear", "confidence": "low", "evidence": []},
        "automation_level": {"value": "Unclear", "confidence": "low", "evidence": []},
        "human_oversight":  {"value": "Unclear", "confidence": "low", "evidence": []},
        "uses_gpai":        {"value": "Unclear", "confidence": "low", "evidence": []}
    },
    "preliminary_assessment": {
        "ai_system": "unclear",
        "ai_system_reasoning": "Insufficient evidence to determine whether the Article 3 inference criterion is met.",
        "ai_system_definition_notes": "The evidence does not show whether the system infers predictions, recommendations, decisions, or content from inputs.",
        "definition_exclusion": "unclear",
        "risk_tier": "unclear",
        "prohibited_practice_subtype": "unclear",
        "high_risk_domain": "unclear",
        "transparency_or_gpai_notes": "Insufficient evidence to assess Article 50 or GPAI relevance.",
        "confidence": "low",
        "reasoning": "The uploaded documents do not contain enough information to perform a meaningful AI Act assessment. Additional documentation is needed before any risk classification can be made.",
        "legal_citations": []
    },
    "governance_observations": [],
    "missing_information": [
        {"topic": "Purpose of the AI system", "why_it_matters": "Required for any AI Act analysis.", "suggested_question": "What is the AI system intended to do?"},
        {"topic": "Affected persons",         "why_it_matters": "Drives risk classification.",      "suggested_question": "Who is affected by the system's outputs?"},
        {"topic": "Deployment context",       "why_it_matters": "Sector affects Annex III mapping.","suggested_question": "In what sector or process is the system deployed?"}
    ],
    "needs_more_evidence": []
})
