"""
Norrin AI Act Compliance Assistant — Streamlit dashboard.

Run with:
    streamlit run app.py

This is the front-end of the multi-agent system. It:
    1. Takes uploaded documents for a single AI use case (one session = one case).
    2. Runs them through preprocessing → chunking → vector store.
    3. Calls run_assessment_pipeline (Assessment → Critic → Revise once → Presenter).
    4. Renders the 6 dashboard sections + warnings + agent history.

Step 11 (follow-up chat) is intentionally a small block at the bottom — answering
a missing-info question is just another piece of session metadata that triggers
a pipeline re-run.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import streamlit as st

from src.config import LLM_PROVIDER, LLM_MODEL, MOCK_LLM
from src.preprocessing import process_uploaded_files
from src.chunking import chunk_document
from src.vector_store import (
    add_chunks_to_uploaded,
    delete_session_chunks,
    get_corpus_collection,
)
from src.pipeline import run_assessment_pipeline


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Norrin AI Act Compliance Assistant",
    page_icon="⚖️",
    layout="wide",
)


def _confidence_badge(confidence: str) -> str:
    icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(confidence, "⚪")
    return f"{icon} {confidence}"


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def _init_state() -> None:
    defaults = {
        "session_id": f"sess_{uuid.uuid4().hex[:8]}",
        "processed_docs": [],
        "chunks": [],
        "pipeline_result": None,
        "session_metadata": {},
        "follow_up_answers": [],
        "is_running": False,
        "clear_follow_up_input": False,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


_init_state()
session_id: str = st.session_state["session_id"]


# ---------------------------------------------------------------------------
# Sidebar — session, configuration, system state
# ---------------------------------------------------------------------------

with st.sidebar:
    st.subheader("Session")
    st.code(session_id, language="text")

    if st.button("Reset session", use_container_width=True):
        delete_session_chunks(session_id)
        for k in ("session_id", "processed_docs", "chunks", "pipeline_result",
                  "session_metadata", "follow_up_answers", "is_running",
                  "clear_follow_up_input", "follow_up_input"):
            st.session_state.pop(k, None)
        st.rerun()

    st.divider()
    st.subheader("Configuration")
    if MOCK_LLM:
        st.success("MOCK_LLM = true\nAgents use fixtures (offline).")
    else:
        st.warning(f"MOCK_LLM = false\nUsing {LLM_PROVIDER} / {LLM_MODEL}")

    try:
        corpus_count = get_corpus_collection().count()
        st.caption(f"AI Act corpus: **{corpus_count}** chunks indexed")
    except Exception as exc:
        st.caption(f"Corpus: unavailable ({exc})")

    st.divider()
    st.subheader("Use case metadata (optional)")
    with st.form("metadata_form", clear_on_submit=False):
        case_name = st.text_input(
            "Use case name",
            value=st.session_state["session_metadata"].get("case_name", ""),
        )
        sector_hint = st.text_input(
            "Sector hint",
            value=st.session_state["session_metadata"].get("sector_hint", ""),
            placeholder="e.g. HR, healthcare, fintech",
        )
        org_role = st.selectbox(
            "Likely role",
            options=["", "provider", "deployer", "both", "unclear"],
            index=["", "provider", "deployer", "both", "unclear"].index(
                st.session_state["session_metadata"].get("org_role", "")
            ),
        )
        if st.form_submit_button("Save metadata", use_container_width=True):
            st.session_state["session_metadata"] = {
                "case_name":   case_name or None,
                "sector_hint": sector_hint or None,
                "org_role":    org_role or None,
            }
            st.toast("Metadata saved")


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("Norrin AI Act Compliance Assistant")
st.caption(
    "Upload documents describing one AI use case → receive a structured, "
    "evidence-grounded preliminary EU AI Act assessment."
)
st.warning(
    "**Not legal advice.** This tool produces a preliminary assessment for "
    "structured review. It does not replace qualified legal counsel.",
    icon="⚠️",
)


# ---------------------------------------------------------------------------
# Stage 1 — Upload documents
# ---------------------------------------------------------------------------

st.header("1. Upload documents for this AI use case")

uploaded_files = st.file_uploader(
    "Drop case studies, product descriptions, vendor white papers, technical "
    "overviews, policy notes, etc. (PDF, DOCX, PPTX, HTML, CSV, TXT, MD)",
    type=["pdf", "docx", "pptx", "html", "htm", "csv", "txt", "md"],
    accept_multiple_files=True,
)

run_disabled = not uploaded_files or st.session_state["is_running"]
run_label = "Analyze" if not st.session_state["is_running"] else "Analysis running…"

if st.button(run_label, type="primary", disabled=run_disabled):
    st.session_state["is_running"] = True
    st.session_state["pipeline_result"] = None
    delete_session_chunks(session_id)  # clear prior chunks for this session

    t_start = time.perf_counter()
    progress = st.progress(0, text="Converting files via MarkItDown…")

    docs = process_uploaded_files(uploaded_files, session_id=session_id)
    st.session_state["processed_docs"] = docs
    progress.progress(25, text="Chunking…")

    chunks: list[dict] = []
    for d in docs:
        chunks.extend(chunk_document(d))
    st.session_state["chunks"] = chunks
    progress.progress(50, text="Embedding and indexing chunks…")

    add_chunks_to_uploaded(chunks)
    progress.progress(70, text="Running multi-agent assessment…")

    metadata = {
        **(st.session_state["session_metadata"] or {}),
        "follow_up_answers": st.session_state["follow_up_answers"],
    }
    result = run_assessment_pipeline(session_id, session_metadata=metadata)
    st.session_state["pipeline_result"] = result
    progress.progress(100, text=f"Done in {time.perf_counter() - t_start:.1f}s")

    st.session_state["is_running"] = False
    st.rerun()


# ---------------------------------------------------------------------------
# Stage 2 — Upload summary
# ---------------------------------------------------------------------------

if st.session_state["processed_docs"]:
    with st.expander("Uploaded documents", expanded=False):
        for d in st.session_state["processed_docs"]:
            error = d.get("error")
            line = f"**{d['filename']}** · type: `{d['document_type']}`"
            if error:
                st.error(f"{line} — {error}")
            else:
                st.write(f"- {line}")
        st.caption(f"{len(st.session_state['chunks'])} chunks indexed for this session.")


# ---------------------------------------------------------------------------
# Stage 3 — Render results
# ---------------------------------------------------------------------------

result = st.session_state["pipeline_result"]

if result is None:
    st.info("Upload at least one document and click **Analyze** to begin.", icon="📄")
    st.stop()


presented = result.get("presented", {})
sections = presented.get("sections", {})
warnings = presented.get("warnings", [])
meta = presented.get("_meta", {})


# Top-of-result banner
st.divider()
st.header("2. Assessment")

if meta.get("revision_triggered"):
    st.caption("Critic flagged the first draft — assessment was revised once.")

for w in warnings:
    sev = w.get("severity", "low")
    msg = w.get("message", "")
    if sev == "high":
        st.error(msg, icon="🛑")
    elif sev == "medium":
        st.warning(msg, icon="⚠️")
    else:
        st.info(msg, icon="ℹ️")


# Summary always visible
summary = sections.get("use_case_summary", {})
st.subheader(summary.get("title", "Use-case summary"))
st.write(summary.get("body", ""))


tab_facts, tab_assess, tab_gov, tab_missing, tab_cites, tab_history = st.tabs([
    "Extracted facts",
    "Preliminary assessment",
    "Governance",
    "Missing info & follow-up",
    "Citations",
    "Pipeline history",
])


# ---- Extracted facts -------------------------------------------------------

with tab_facts:
    facts = sections.get("extracted_facts", {}).get("facts", [])
    if not facts:
        st.caption("No facts extracted.")
    else:
        for f in facts:
            cols = st.columns([2, 5, 2, 3])
            cols[0].markdown(f"**{f['label']}**")
            cols[1].write(f["value"])
            cols[2].markdown(_confidence_badge(f["confidence"]))
            cols[3].caption(
                f"evidence: {', '.join(f['evidence']) if f['evidence'] else '—'}"
            )


# ---- Preliminary assessment ------------------------------------------------

with tab_assess:
    pa = sections.get("preliminary_assessment", {})
    if not pa:
        st.caption("No assessment produced.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("AI system",  pa["ai_system"]["label"])
        c2.metric("Risk tier",  pa["risk_tier"]["label"])
        c3.metric("Confidence", pa["confidence"]["value"])

        if pa["ai_system"].get("reasoning"):
            st.markdown("**Why this is an AI system**")
            st.write(pa["ai_system"]["reasoning"])

        if pa["ai_system"].get("definition_notes"):
            st.markdown("**AI system definition notes**")
            st.write(pa["ai_system"]["definition_notes"])
        if pa["ai_system"].get("definition_exclusion"):
            st.caption(f"Definition exclusion considered: `{pa['ai_system']['definition_exclusion']}`")

        risk_details = []
        subtype = pa["risk_tier"].get("prohibited_practice_subtype")
        high_risk_domain = pa["risk_tier"].get("high_risk_domain")
        if subtype and subtype != "none":
            risk_details.append(f"prohibited subtype: `{subtype}`")
        if high_risk_domain and high_risk_domain != "none":
            risk_details.append(f"high-risk domain: `{high_risk_domain}`")
        if risk_details:
            st.caption(" · ".join(risk_details))

        if pa.get("transparency_or_gpai_notes"):
            st.markdown("**Transparency / GPAI notes**")
            st.write(pa["transparency_or_gpai_notes"])

        st.markdown("**Reasoning**")
        st.write(pa.get("reasoning", ""))

        st.markdown("**Legal citations**")
        cites = pa.get("legal_citations", [])
        if cites:
            for c in cites:
                st.code(c, language="text")
        else:
            st.caption("No legal citations attached.")


# ---- Governance ------------------------------------------------------------

with tab_gov:
    items = sections.get("governance_observations", {}).get("items", [])
    if not items:
        st.caption("No governance observations.")
    else:
        for item in items:
            with st.container(border=True):
                st.markdown(f"**{item['area_label']}**")
                st.write(item["observation"])
                if item["citations"]:
                    st.caption("cites: " + ", ".join(item["citations"]))


# ---- Missing info + follow-up ----------------------------------------------

with tab_missing:
    miss_section = sections.get("missing_information", {})
    missing = miss_section.get("missing", [])
    follow_ups = miss_section.get("follow_up_questions", [])

    st.markdown("**Identified gaps**")
    if missing:
        for m in missing:
            with st.container(border=True):
                st.markdown(f"**{m['topic']}**")
                if m["why_it_matters"]:
                    st.caption(m["why_it_matters"])
                if m["suggested_question"]:
                    st.write(f"_Suggested question:_ {m['suggested_question']}")
    else:
        st.caption("No gaps flagged.")

    st.markdown("**Follow-up questions to ask**")
    if follow_ups:
        for q in follow_ups:
            st.write(f"- {q}")
    else:
        st.caption("No follow-ups suggested.")

    st.divider()
    st.markdown("**Provide more information**")
    st.caption(
        "Add answers or new context here. Clicking *Apply* will append your input to "
        "the session and re-run the multi-agent pipeline."
    )
    if st.session_state.pop("clear_follow_up_input", False):
        st.session_state["follow_up_input"] = ""
    new_answer = st.text_area(
        "Additional context", key="follow_up_input", height=100,
        placeholder="e.g. 'A recruiter must explicitly approve every shortlisted candidate.'",
    )
    if st.button("Apply and re-run"):
        if new_answer.strip():
            st.session_state["follow_up_answers"].append(new_answer.strip())
            st.session_state["clear_follow_up_input"] = True
            sample_dir = Path("data") / "uploaded" / session_id
            sample_dir.mkdir(parents=True, exist_ok=True)
            follow_up_path = sample_dir / f"follow_up_{len(st.session_state['follow_up_answers'])}.md"
            follow_up_path.write_text(
                f"# Follow-up clarification\n\n{new_answer.strip()}\n",
                encoding="utf-8",
            )
            docs = process_uploaded_files([follow_up_path], session_id=session_id)
            chunks: list[dict] = []
            for d in docs:
                chunks.extend(chunk_document(d))
            add_chunks_to_uploaded(chunks)

            metadata = {
                **(st.session_state["session_metadata"] or {}),
                "follow_up_answers": st.session_state["follow_up_answers"],
            }
            with st.spinner("Re-running pipeline with new context…"):
                st.session_state["pipeline_result"] = run_assessment_pipeline(
                    session_id, session_metadata=metadata
                )
            st.rerun()


# ---- Citations -------------------------------------------------------------

with tab_cites:
    cit = sections.get("citations", {})
    col_u, col_c = st.columns(2)

    with col_u:
        st.markdown("**Uploaded evidence**")
        items = cit.get("uploaded_evidence", [])
        if items:
            for c in items:
                st.code(c["chunk_id"], language="text")
        else:
            st.caption("None cited.")

    with col_c:
        st.markdown("**Corpus citations (EU AI Act)**")
        items = cit.get("corpus_citations", [])
        if items:
            for c in items:
                st.code(c["chunk_id"], language="text")
        else:
            st.caption("None cited.")


# ---- Pipeline history (multi-agent transparency) --------------------------

with tab_history:
    st.caption(
        "Stage-by-stage log of the multi-agent run. Each entry shows an agent's "
        "output exactly as it was produced."
    )
    history = result.get("history", [])
    for h in history:
        stage = h["stage"]
        out = h["output"]
        with st.expander(f"{stage}", expanded=False):
            if stage.startswith("assessment"):
                pa = out.get("preliminary_assessment", {})
                st.write(
                    f"**risk_tier:** `{pa.get('risk_tier')}` · "
                    f"**confidence:** `{pa.get('confidence')}` · "
                    f"**was_revision:** `{out.get('_meta', {}).get('was_revision')}`"
                )
            elif stage.startswith("critic"):
                st.write(
                    f"**pass:** `{out.get('pass')}` · "
                    f"**issues:** {len(out.get('issues', []))}"
                )
                if out.get("revision_instruction"):
                    st.write(f"**revision_instruction:** {out['revision_instruction']}")
            elif stage == "presenter":
                st.write(f"**warnings:** {len(out.get('warnings', []))}")
                st.write(f"**sections:** {', '.join(out.get('_meta', {}).get('sections_present', []))}")
            st.json(out, expanded=False)


# ---------------------------------------------------------------------------
# Footer — disclaimer + provenance
# ---------------------------------------------------------------------------

st.divider()
st.caption(presented.get("disclaimer", ""))
st.caption(
    f"Multi-agent run: revision_triggered={meta.get('revision_triggered')} · "
    f"iterations={meta.get('iterations')} · critic_pass={meta.get('critic_pass')}"
)
