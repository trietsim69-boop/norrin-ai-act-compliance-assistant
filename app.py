"""
Norrin AI Act Compliance Assistant — Streamlit dashboard (dark theme).

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import html
import time
import uuid
from pathlib import Path

import streamlit as st

from src.config import MOCK_LLM
from src.preprocessing import process_uploaded_files, process_manual_description
from src.chunking import chunk_document
from src.vector_store import (
    add_chunks_to_uploaded,
    delete_session_chunks,
)
from src.pipeline import run_assessment_pipeline


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

def _inject_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Serif:wght@400;600&display=swap');

        :root {
            --bg-deep: #070b14;
            --bg-main: #0a1020;
            --bg-panel: #111827;
            --bg-card: #151f33;
            --border: rgba(148, 163, 184, 0.14);
            --border-accent: rgba(96, 165, 250, 0.35);
            --text: #e2e8f0;
            --text-muted: #94a3b8;
            --accent: #60a5fa;
            --accent-soft: rgba(96, 165, 250, 0.12);
            --success: #34d399;
            --warning: #fbbf24;
            --danger: #f87171;
            --serif: "IBM Plex Serif", Georgia, serif;
            --sans: "IBM Plex Sans", system-ui, sans-serif;
            --mono: "IBM Plex Mono", ui-monospace, monospace;
        }

        .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            background: var(--bg-deep) !important;
            color: var(--text);
            font-family: var(--sans);
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0c1222 0%, #0a0f1c 100%) !important;
            border-right: 1px solid var(--border);
        }

        [data-testid="stSidebar"] .block-container {
            padding-top: 1.25rem;
        }

        h1, h2, h3, .norrin-title {
            font-family: var(--serif) !important;
            font-weight: 600 !important;
            letter-spacing: -0.01em;
        }

        h1 { color: #f8fafc !important; font-size: 2.35rem !important; }
        h2, h3 { color: #f1f5f9 !important; }

        code, .stCode, .session-pill, [data-testid="stCode"] {
            font-family: var(--mono) !important;
        }

        p, label, .stMarkdown, .stCaption, [data-testid="stWidgetLabel"] {
            font-family: var(--sans) !important;
        }

        #MainMenu, footer, header[data-testid="stHeader"] {
            visibility: hidden;
            height: 0 !important;
        }

        .block-container {
            padding-top: 1.5rem;
            max-width: 1180px;
        }

        /* Sidebar brand */
        .sidebar-brand {
            display: flex;
            align-items: center;
            gap: 0.65rem;
            margin-bottom: 1.5rem;
        }
        .sidebar-brand-icon {
            width: 36px; height: 36px;
            border-radius: 10px;
            background: var(--accent-soft);
            border: 1px solid var(--border-accent);
            display: flex; align-items: center; justify-content: center;
            font-size: 1.1rem;
        }
        .sidebar-brand-text {
            line-height: 1.15;
        }
        .sidebar-brand-text strong {
            display: block;
            font-family: var(--sans);
            font-size: 0.95rem;
            font-weight: 700;
            color: #f8fafc;
        }
        .sidebar-brand-text span {
            font-size: 0.62rem;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: var(--text-muted);
        }

        .sidebar-label {
            font-size: 0.68rem;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: var(--text-muted);
            margin: 1rem 0 0.35rem;
            font-weight: 600;
        }

        .session-pill {
            background: #0f172a;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.55rem 0.75rem;
            font-family: var(--mono);
            font-size: 0.76rem;
            color: #cbd5e1;
            margin-bottom: 0.5rem;
        }

        .case-context-bar {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 0.85rem 1rem;
            margin: 0.75rem 0 1.25rem;
            font-size: 0.84rem;
        }
        .case-context-bar .case-title {
            font-family: var(--serif);
            font-size: 1.05rem;
            color: #f8fafc;
            margin-bottom: 0.35rem;
        }
        .case-context-bar .case-meta {
            color: var(--text-muted);
            font-size: 0.78rem;
        }
        .case-context-bar .case-files {
            margin-top: 0.45rem;
            font-family: var(--mono);
            font-size: 0.72rem;
            color: #94a3b8;
        }

        .view-kicker-results {
            color: var(--success);
        }

        .config-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.35rem 0.65rem;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 600;
            margin-bottom: 0.45rem;
        }
        .config-badge.mock-on {
            background: rgba(52, 211, 153, 0.12);
            color: var(--success);
            border: 1px solid rgba(52, 211, 153, 0.25);
        }
        .config-badge.mock-off {
            background: rgba(251, 191, 36, 0.12);
            color: var(--warning);
            border: 1px solid rgba(251, 191, 36, 0.25);
        }
        .config-line {
            font-size: 0.78rem;
            color: var(--text-muted);
            margin: 0.15rem 0;
        }

        .sidebar-hint {
            font-size: 0.78rem;
            color: var(--text-muted);
            line-height: 1.45;
            margin: 0.25rem 0 0.65rem;
        }
        .sidebar-question {
            font-size: 0.78rem;
            color: #cbd5e1;
            padding: 0.45rem 0.55rem;
            margin-bottom: 0.35rem;
            background: #0f172a;
            border-radius: 8px;
            border-left: 2px solid var(--accent);
            line-height: 1.4;
        }
        .sidebar-prior {
            font-size: 0.76rem;
            color: var(--text-muted);
            padding: 0.35rem 0;
            border-bottom: 1px solid var(--border);
        }

        /* Main header */
        .page-kicker {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            font-size: 0.68rem;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: var(--accent);
            margin-bottom: 0.75rem;
            font-weight: 600;
        }
        .page-subtitle {
            color: var(--text-muted);
            font-size: 1rem;
            max-width: 720px;
            margin-bottom: 1.25rem;
        }
        .demo-pill {
            float: right;
            font-size: 0.72rem;
            color: var(--text-muted);
            border: 1px solid var(--border);
            border-radius: 999px;
            padding: 0.25rem 0.65rem;
            margin-top: 0.35rem;
        }

        .disclaimer-box {
            background: rgba(249, 115, 22, 0.08);
            border: 1px solid rgba(249, 115, 22, 0.35);
            border-radius: 12px;
            padding: 0.85rem 1rem;
            margin: 1rem 0 1.5rem;
            display: flex;
            gap: 0.65rem;
            align-items: flex-start;
        }
        .disclaimer-box strong { color: #fdba74; }
        .disclaimer-box span { color: #fcd34d; font-size: 1rem; line-height: 1; margin-top: 0.1rem; }

        .section-heading {
            font-family: var(--serif) !important;
            font-size: 1.35rem !important;
            color: #f8fafc !important;
            margin: 1.5rem 0 0.75rem !important;
        }

        /* Upload dropzone */
        [data-testid="stFileUploader"] section[data-testid="stFileUploadDropzone"] {
            background: rgba(15, 23, 42, 0.55) !important;
            border: 2px dashed rgba(96, 165, 250, 0.38) !important;
            border-radius: 14px !important;
            padding: 2rem 1.5rem !important;
        }
        [data-testid="stFileUploader"] section[data-testid="stFileUploadDropzone"]:hover {
            border-color: rgba(96, 165, 250, 0.65) !important;
            background: rgba(30, 41, 59, 0.45) !important;
        }
        [data-testid="stFileUploader"] small {
            color: var(--text-muted) !important;
        }

        /* Inputs */
        .stTextArea textarea, .stTextInput input, .stSelectbox div[data-baseweb="select"] {
            background: #0f172a !important;
            border-color: var(--border) !important;
            color: var(--text) !important;
            border-radius: 10px !important;
        }

        /* Buttons */
        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #2563eb, #3b82f6) !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            padding: 0.55rem 1.25rem !important;
        }
        .stButton > button {
            border-radius: 10px !important;
            border: 1px solid var(--border) !important;
            background: #111827 !important;
            color: var(--text) !important;
        }

        /* Progress */
        .stProgress > div > div > div > div {
            background: linear-gradient(90deg, #2563eb, #60a5fa, #93c5fd) !important;
            background-size: 200% 100%;
            animation: progress-shimmer 1.8s ease-in-out infinite;
        }
        @keyframes progress-shimmer {
            0% { background-position: 100% 0; }
            100% { background-position: -100% 0; }
        }

        /* Overview cards */
        .overview-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 1rem 1.1rem;
            min-height: 96px;
        }
        .overview-card .label {
            font-size: 0.68rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--text-muted);
            margin-bottom: 0.45rem;
            font-weight: 600;
        }
        .overview-card .value {
            font-family: var(--serif);
            font-size: 1.35rem;
            font-weight: 600;
            color: #f8fafc;
            line-height: 1.2;
        }
        .overview-card.tone-success { border-color: rgba(52, 211, 153, 0.35); }
        .overview-card.tone-success .value { color: #6ee7b7; }
        .overview-card.tone-warning { border-color: rgba(251, 191, 36, 0.35); }
        .overview-card.tone-warning .value { color: #fcd34d; }
        .overview-card.tone-danger { border-color: rgba(248, 113, 113, 0.35); }
        .overview-card.tone-danger .value { color: #fca5a5; }
        .overview-card.tone-info { border-color: rgba(96, 165, 250, 0.35); }
        .overview-card.tone-info .value { color: #93c5fd; }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.35rem;
            background: transparent;
            border-bottom: 1px solid var(--border);
        }
        .stTabs [data-baseweb="tab"] {
            background: transparent;
            color: var(--text-muted);
            border-radius: 8px 8px 0 0;
            font-size: 0.82rem;
            font-weight: 500;
        }
        .stTabs [aria-selected="true"] {
            background: var(--bg-card) !important;
            color: var(--accent) !important;
            border: 1px solid var(--border);
            border-bottom-color: var(--bg-card) !important;
        }

        /* Citation cards */
        .citation-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1rem 1.1rem;
            margin-bottom: 0.75rem;
        }
        .citation-card .cat {
            font-size: 0.68rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--accent);
            margin-bottom: 0.5rem;
        }
        .citation-row {
            margin: 0.35rem 0;
            font-size: 0.88rem;
            line-height: 1.45;
        }
        .citation-row strong {
            color: #cbd5e1;
            font-weight: 600;
        }
        .citation-excerpt {
            margin-top: 0.65rem;
            padding: 0.65rem 0.75rem;
            background: #0f172a;
            border-left: 3px solid var(--accent);
            border-radius: 0 8px 8px 0;
            color: #cbd5e1;
            font-style: italic;
            font-size: 0.86rem;
        }
        .citation-why {
            margin-top: 0.55rem;
            font-size: 0.82rem;
            color: var(--text-muted);
        }

        /* Fact rows */
        .fact-row {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 0.75rem 1rem;
            margin-bottom: 0.5rem;
        }

        /* Follow-up chat */
        .followup-panel {
            background: var(--bg-panel);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 1.1rem 1.25rem;
            margin-top: 1.5rem;
        }
        .followup-panel h4 {
            font-family: var(--serif) !important;
            color: #f8fafc;
            margin: 0 0 0.35rem;
            font-size: 1.15rem;
        }

        /* Agent trace */
        .trace-stage {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 0.65rem 0.85rem;
            margin-bottom: 0.45rem;
            font-size: 0.82rem;
        }
        .trace-stage strong { color: var(--accent); }

        div[data-testid="stMetric"] {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 0.75rem;
        }
        div[data-testid="stMetricLabel"] { color: var(--text-muted) !important; }
        div[data-testid="stMetricValue"] {
            font-family: var(--serif) !important;
            color: #f8fafc !important;
        }

        [data-testid="stExpander"] {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 10px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _esc(text: str) -> str:
    return html.escape(str(text or ""))


def _risk_tone(risk_label: str) -> str:
    lower = (risk_label or "").lower()
    if any(k in lower for k in ("prohibited", "unacceptable", "high")):
        return "tone-danger"
    if any(k in lower for k in ("limited", "transparency")):
        return "tone-warning"
    if any(k in lower for k in ("minimal", "low")):
        return "tone-success"
    if any(k in lower for k in ("gpai", "unclear")):
        return "tone-info"
    return "tone-info"


def _confidence_tone(confidence: str) -> str:
    return {
        "high": "tone-success",
        "medium": "tone-warning",
        "low": "tone-danger",
    }.get((confidence or "").lower(), "tone-info")


def _overview_card(label: str, value: str, tone: str = "tone-info") -> str:
    return f"""
    <div class="overview-card {tone}">
        <div class="label">{_esc(label)}</div>
        <div class="value">{_esc(value)}</div>
    </div>
    """


def _render_citation_card(card: dict, *, show_claim: bool = True) -> None:
    category = card.get("evidence_category_label") or card.get("evidence_category") or ""
    claim = card.get("claim") or ""
    source = card.get("source") or card.get("source_label") or "—"
    ev_type = card.get("evidence_type") or "Unknown"
    excerpt = (card.get("excerpt") or "").strip()
    explanation = (card.get("relevance_explanation") or "").strip()
    layer = card.get("law_layer_label")
    topic = card.get("topic_label")

    rows = []
    if show_claim and claim:
        rows.append(f'<div class="citation-row"><strong>Claim:</strong> {_esc(claim)}</div>')
    rows.append(f'<div class="citation-row"><strong>Source:</strong> {_esc(source)}</div>')
    rows.append(f'<div class="citation-row"><strong>Type:</strong> {_esc(ev_type)}</div>')
    if layer:
        rows.append(f'<div class="citation-row"><strong>Layer:</strong> {_esc(layer)}</div>')
    if topic:
        rows.append(f'<div class="citation-row"><strong>Topic:</strong> {_esc(topic)}</div>')

    excerpt_html = ""
    if excerpt:
        excerpt_html = f'<div class="citation-excerpt">"{_esc(excerpt)}"</div>'
    elif show_claim:
        excerpt_html = '<div class="citation-row" style="color:var(--text-muted)">Evidence excerpt not available.</div>'

    why_html = ""
    if explanation:
        why_html = f'<div class="citation-why"><strong>Why this supports the claim:</strong> {_esc(explanation)}</div>'

    cat_html = f'<div class="cat">{_esc(category)}</div>' if category else ""

    st.markdown(
        f'<div class="citation-card">{cat_html}{"".join(rows)}{excerpt_html}{why_html}</div>',
        unsafe_allow_html=True,
    )

    full = (card.get("full_text") or (card.get("_resolved") or {}).get("full_text") or "").strip()
    if full:
        with st.expander(f"View full source text ({len(full.split())} words)", expanded=False):
            st.text(full)


def _confidence_badge(confidence: str) -> str:
    icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(confidence, "⚪")
    return f"{icon} {confidence}"


def _collect_suggested_questions(result: dict | None) -> list[str]:
    if not result:
        return []
    presented = result.get("presented") or {}
    miss = (presented.get("sections") or {}).get("missing_information") or {}
    out: list[str] = []
    for q in miss.get("follow_up_questions") or []:
        if q and q not in out:
            out.append(q)
    for item in miss.get("missing") or []:
        q = item.get("suggested_question")
        if q and q not in out:
            out.append(q)
    critic_qs = (result.get("critic") or {}).get("missing_questions") or []
    for q in critic_qs:
        if q and q not in out:
            out.append(q)
    return out[:6]


def _apply_follow_up(session_id: str, answer: str) -> None:
    st.session_state["follow_up_answers"].append(answer.strip())
    st.session_state["clear_follow_up_input"] = True
    st.session_state["app_view"] = "results"
    sample_dir = Path("data") / "uploaded" / session_id
    sample_dir.mkdir(parents=True, exist_ok=True)
    follow_up_path = sample_dir / f"follow_up_{len(st.session_state['follow_up_answers'])}.md"
    follow_up_path.write_text(
        f"# Follow-up clarification\n\n{answer.strip()}\n",
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
    with st.spinner("Updating assessment…"):
        st.session_state["pipeline_result"] = run_assessment_pipeline(
            session_id, session_metadata=metadata
        )


def _reset_session() -> None:
    sid = st.session_state.get("session_id")
    if sid:
        delete_session_chunks(sid)
    for k in (
        "session_id", "processed_docs", "chunks", "pipeline_result",
        "session_metadata", "follow_up_answers", "is_running",
        "clear_follow_up_input", "app_view",
    ):
        st.session_state.pop(k, None)


def _case_context_html() -> str:
    meta = st.session_state.get("session_metadata") or {}
    case_name = meta.get("case_name") or "Assessment report"
    sector = meta.get("sector_hint")
    role = meta.get("org_role")
    meta_bits = [b for b in (sector, role) if b]
    meta_line = " · ".join(meta_bits) if meta_bits else "Preliminary EU AI Act review"

    files = [
        d["filename"]
        for d in (st.session_state.get("processed_docs") or [])
        if not d.get("error")
    ]
    files_line = ", ".join(files) if files else "Manual description"
    n_chunks = len(st.session_state.get("chunks") or [])

    return f"""
    <div class="case-context-bar">
        <div class="case-title">{_esc(case_name)}</div>
        <div class="case-meta">{_esc(meta_line)} · {_esc(n_chunks)} indexed chunks</div>
        <div class="case-files">{_esc(files_line)}</div>
    </div>
    """


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Norrin AI Act Compliance Assistant",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

_inject_theme()


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
        "app_view": "intake",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

    if st.session_state.get("pipeline_result") is not None:
        st.session_state["app_view"] = "results"


_init_state()
session_id: str = st.session_state["session_id"]
app_view: str = st.session_state["app_view"]
has_results = app_view == "results" and st.session_state["pipeline_result"] is not None
sidebar_questions = _collect_suggested_questions(st.session_state.get("pipeline_result"))


# ---------------------------------------------------------------------------
# Sidebar — case context, follow-up, session controls
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-brand-icon">⚖️</div>
            <div class="sidebar-brand-text">
                <strong>Norrin</strong>
                <span>AI Act Compliance</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="sidebar-label">About this case</div>', unsafe_allow_html=True)
    st.caption("Optional — helps tailor the assessment.")
    with st.form("metadata_form", clear_on_submit=False):
        case_name = st.text_input(
            "What are you assessing?",
            value=st.session_state["session_metadata"].get("case_name", ""),
            placeholder="e.g. Recruitment screening AI",
        )
        sector_hint = st.text_input(
            "Industry / sector",
            value=st.session_state["session_metadata"].get("sector_hint", ""),
            placeholder="HR, healthcare, fintech…",
        )
        org_role = st.selectbox(
            "Your organisation's role",
            options=["", "provider", "deployer", "both", "unclear"],
            index=["", "provider", "deployer", "both", "unclear"].index(
                st.session_state["session_metadata"].get("org_role", "")
            ),
        )
        if st.form_submit_button("Save case details", use_container_width=True):
            st.session_state["session_metadata"] = {
                "case_name": case_name or None,
                "sector_hint": sector_hint or None,
                "org_role": org_role or None,
            }
            st.toast("Case details saved")

    st.markdown('<div class="sidebar-label">Refine the assessment</div>', unsafe_allow_html=True)

    if not has_results:
        st.markdown(
            '<p class="sidebar-hint">Run your first analysis from the main page. '
            "Then come back here to answer open questions and update the results.</p>",
            unsafe_allow_html=True,
        )
    else:
        if sidebar_questions:
            st.caption("Open questions from the assessment:")
            for q in sidebar_questions:
                st.markdown(f'<div class="sidebar-question">{_esc(q)}</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                '<p class="sidebar-hint">No specific follow-ups flagged — '
                "you can still add clarifications below.</p>",
                unsafe_allow_html=True,
            )

        if st.session_state.get("clear_follow_up_input"):
            st.session_state["follow_up_input"] = ""
            st.session_state["clear_follow_up_input"] = False

        st.text_area(
            "Your answer or new context",
            key="follow_up_input",
            height=110,
            placeholder="e.g. Recruiters must approve every shortlist before candidates are contacted.",
            label_visibility="collapsed",
        )

        if st.button("Update assessment", type="primary", use_container_width=True):
            answer = st.session_state.get("follow_up_input", "")
            if answer.strip():
                _apply_follow_up(session_id, answer.strip())
                st.rerun()
            else:
                st.toast("Add a short answer first.")

        if st.session_state["follow_up_answers"]:
            with st.expander(
                f"Previous updates ({len(st.session_state['follow_up_answers'])})",
                expanded=False,
            ):
                for i, ans in enumerate(st.session_state["follow_up_answers"], start=1):
                    preview = ans if len(ans) <= 120 else ans[:117] + "…"
                    st.markdown(
                        f'<div class="sidebar-prior"><strong>#{i}</strong> {_esc(preview)}</div>',
                        unsafe_allow_html=True,
                    )

    st.divider()

    if st.button("↺  New assessment", use_container_width=True):
        _reset_session()
        st.rerun()

    with st.expander("Session reference", expanded=False):
        st.code(session_id, language="text")
        if MOCK_LLM:
            st.caption("Demo mode — using offline fixtures.")


# ---------------------------------------------------------------------------
# Main — intake vs results (separate views)
# ---------------------------------------------------------------------------

if app_view == "intake":
    st.markdown(
        """
        <div>
            <span class="demo-pill">Hackathon demo · v0.1</span>
            <div class="page-kicker">⚖ EU AI ACT COMPLIANCE · NEW CASE</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.title("Norrin AI Act Compliance Assistant")
    st.markdown(
        '<p class="page-subtitle">Submit your AI use case once — documents, a short description, '
        "or both. You'll land on a dedicated assessment report when analysis completes.</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="disclaimer-box">
            <span>⚠</span>
            <div><strong>Not legal advice.</strong> This tool produces a preliminary assessment for
            structured review. It does not replace qualified legal counsel.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<h3 class="section-heading">Submit this AI use case</h3>', unsafe_allow_html=True)

    uploaded_files = st.file_uploader(
        "Upload documents (optional)",
        type=["pdf", "docx", "pptx", "html", "htm", "csv", "txt", "md"],
        accept_multiple_files=True,
        help="PDF, DOCX, PPTX, HTML, CSV, TXT, or MD.",
        label_visibility="collapsed",
    )

    st.markdown("**Or describe the AI use case manually**")

    manual_description = st.text_area(
        "Use-case description",
        height=120,
        placeholder=(
            "Example: We use an AI tool to rank job applicants based on CVs and interview "
            "transcripts. Recruiters review the top candidates before interview decisions."
        ),
        label_visibility="collapsed",
    )

    has_files = bool(uploaded_files)
    has_manual = bool(manual_description.strip())
    run_disabled = (not has_files and not has_manual) or st.session_state["is_running"]
    run_label = "Run assessment" if not st.session_state["is_running"] else "Analysis running…"

    if st.button(run_label, type="primary", disabled=run_disabled, use_container_width=False):
        st.session_state["is_running"] = True
        st.session_state["pipeline_result"] = None
        delete_session_chunks(session_id)

        t_start = time.perf_counter()
        progress = st.progress(0, text="Preparing input…")

        docs: list[dict] = []
        if uploaded_files:
            progress.progress(12, text="Converting files via MarkItDown…")
            docs.extend(process_uploaded_files(uploaded_files, session_id=session_id))
        if has_manual:
            docs.append(process_manual_description(manual_description, session_id=session_id))

        st.session_state["processed_docs"] = docs
        progress.progress(28, text="Chunking documents…")

        chunks: list[dict] = []
        for d in docs:
            if d.get("error"):
                continue
            chunks.extend(chunk_document(d))
        st.session_state["chunks"] = chunks
        progress.progress(52, text="Embedding and indexing…")

        add_chunks_to_uploaded(chunks)
        progress.progress(72, text="Running Assessment → Critic → Presenter…")

        metadata = {
            **(st.session_state["session_metadata"] or {}),
            "follow_up_answers": st.session_state["follow_up_answers"],
        }
        if has_manual:
            metadata["manual_use_case_description"] = manual_description.strip()
        result = run_assessment_pipeline(session_id, session_metadata=metadata)
        st.session_state["pipeline_result"] = result
        progress.progress(100, text=f"Done in {time.perf_counter() - t_start:.1f}s")

        st.session_state["is_running"] = False
        st.session_state["app_view"] = "results"
        st.rerun()

    st.stop()


# --- Results view -----------------------------------------------------------

result = st.session_state.get("pipeline_result")
if result is None:
    st.session_state["app_view"] = "intake"
    st.rerun()

st.markdown(
    """
    <div>
        <span class="demo-pill">Hackathon demo · v0.1</span>
        <div class="page-kicker view-kicker-results">⚖ ASSESSMENT REPORT</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.title("Preliminary EU AI Act Assessment")
st.markdown(_case_context_html(), unsafe_allow_html=True)

presented = result.get("presented", {})
sections = presented.get("sections", {})
warnings = presented.get("warnings", [])
meta = presented.get("_meta", {})
critic = result.get("critic", {})
pa_section = sections.get("preliminary_assessment", {})


# Overview cards
ai_label = pa_section.get("ai_system", {}).get("label", "—")
risk_label = pa_section.get("risk_tier", {}).get("label", "—")
conf_val = pa_section.get("confidence", {}).get("value", "—")
critic_pass = critic.get("pass")
critic_label = "Pass" if critic_pass else "Revise" if critic_pass is False else "—"
critic_tone = "tone-success" if critic_pass else "tone-warning" if critic_pass is False else "tone-info"

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(_overview_card("AI system", ai_label, "tone-info"), unsafe_allow_html=True)
with c2:
    st.markdown(_overview_card("Risk tier", risk_label, _risk_tone(risk_label)), unsafe_allow_html=True)
with c3:
    st.markdown(_overview_card("Confidence", conf_val, _confidence_tone(conf_val)), unsafe_allow_html=True)
with c4:
    st.markdown(_overview_card("Critic verdict", critic_label, critic_tone), unsafe_allow_html=True)

if meta.get("revision_triggered"):
    st.caption("Critic flagged the first draft — assessment was revised once.")

for w in warnings:
    sev = w.get("severity", "low")
    msg = w.get("message", "")
    if sev == "high":
        st.error(msg)
    elif sev == "medium":
        st.warning(msg)
    else:
        st.info(msg)

summary = sections.get("use_case_summary", {})
st.markdown(f'<h3 class="section-heading">{_esc(summary.get("title", "Use-case summary"))}</h3>', unsafe_allow_html=True)
st.write(summary.get("body", ""))

(
    tab_facts,
    tab_assess,
    tab_gov,
    tab_missing,
    tab_cites,
    tab_trace,
) = st.tabs([
    "Extracted facts",
    "Preliminary assessment",
    "Governance",
    "Missing info",
    "Citations",
    "Agent trace",
])


with tab_facts:
    facts = sections.get("extracted_facts", {}).get("facts", [])
    if not facts:
        st.caption("No facts extracted.")
    else:
        for f in facts:
            evidence = (
                "; ".join(
                    r.get("source") or r.get("source_label") or r.get("chunk_id", "?")
                    for r in (f.get("evidence_resolved") or [])
                )
                if f.get("evidence_resolved")
                else "—"
            )
            st.markdown(
                f"""
                <div class="fact-row">
                    <strong>{_esc(f['label'])}</strong>
                    <div style="margin:0.35rem 0;color:#e2e8f0">{_esc(f['value'])}</div>
                    <div style="font-size:0.78rem;color:var(--text-muted)">
                        {_confidence_badge(f['confidence'])} · evidence: {_esc(evidence)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


with tab_assess:
    pa = sections.get("preliminary_assessment", {})
    if not pa:
        st.caption("No assessment produced.")
    else:
        if pa["ai_system"].get("reasoning"):
            st.markdown("**Why this is an AI system**")
            st.write(pa["ai_system"]["reasoning"])
        st.markdown("**Reasoning**")
        st.write(pa.get("reasoning", ""))
        st.markdown("**Legal citations**")
        resolved_cites = pa.get("legal_citations_resolved") or []
        if resolved_cites:
            for r in resolved_cites:
                _render_citation_card(
                    {
                        "claim": "Legal basis for preliminary assessment",
                        "source": r.get("source") or r.get("source_label"),
                        "evidence_type": r.get("evidence_type"),
                        "excerpt": r.get("excerpt"),
                        "relevance_explanation": r.get("relevance_explanation"),
                    },
                )
        else:
            st.caption("No legal citations attached.")


with tab_gov:
    items = sections.get("governance_observations", {}).get("items", [])
    if not items:
        st.caption("No governance observations.")
    else:
        for item in items:
            with st.container(border=True):
                st.markdown(f"**{item['area_label']}**")
                st.write(item["observation"])
                resolved = item.get("citations_resolved") or []
                if resolved:
                    labels = [
                        r.get("source") or r.get("source_label") or r.get("chunk_id", "?")
                        for r in resolved
                    ]
                    st.caption("cites: " + " · ".join(labels))


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

    st.info(
        "Use the **Refine the assessment** panel in the sidebar to answer these "
        "questions and re-run the analysis.",
        icon="💬",
    )


with tab_cites:
    cit = sections.get("citations", {})
    primary = cit.get("citation_cards") or cit.get("claims_table") or []
    additional = cit.get("additional_evidence") or []
    inference = cit.get("system_inference") or {}

    st.markdown("**System inference (conclusions, not direct quotes)**")
    st.caption(inference.get("note", ""))
    if inference.get("ai_system_reasoning"):
        st.markdown("**AI system conclusion**")
        st.write(inference["ai_system_reasoning"])
    if inference.get("risk_reasoning"):
        st.markdown("**Risk classification conclusion**")
        st.write(inference["risk_reasoning"])

    st.divider()
    st.markdown("**Supported facts and regulatory references**")
    if primary:
        for row in primary:
            _render_citation_card(row)
    else:
        st.caption("No strong primary citations for this assessment.")

    if additional:
        with st.expander(f"Additional retrieved evidence ({len(additional)} weaker matches)", expanded=False):
            for row in additional:
                _render_citation_card(row)

    with st.expander("Advanced / debug — raw chunk IDs", expanded=False):
        debug_rows = [
            {
                "chunk_id": row.get("chunk_id", ""),
                "relevance_score": row.get("relevance_score"),
                "display_tier": row.get("display_tier"),
                "resolver": (row.get("_resolved") or {}).get("resolver", ""),
            }
            for row in primary + additional
        ]
        if debug_rows:
            st.dataframe(debug_rows, use_container_width=True, hide_index=True)
        else:
            st.caption("No chunk IDs to show.")


with tab_trace:
    st.caption("Assessment → Critic → (optional revision) → Presenter")
    history = result.get("history", [])
    for h in history:
        stage = h["stage"]
        out = h["output"]
        summary_line = ""
        if stage.startswith("assessment"):
            pa_out = out.get("preliminary_assessment", {})
            summary_line = (
                f"risk_tier={pa_out.get('risk_tier')} · "
                f"confidence={pa_out.get('confidence')}"
            )
        elif stage.startswith("critic"):
            summary_line = (
                f"pass={out.get('pass')} · issues={len(out.get('issues', []))}"
            )
        elif stage == "presenter":
            summary_line = f"warnings={len(out.get('warnings', []))}"

        st.markdown(
            f'<div class="trace-stage"><strong>{_esc(stage)}</strong> — {_esc(summary_line)}</div>',
            unsafe_allow_html=True,
        )
        with st.expander(f"View {stage} output", expanded=False):
            st.json(out, expanded=False)


st.divider()
st.caption(presented.get("disclaimer", ""))
