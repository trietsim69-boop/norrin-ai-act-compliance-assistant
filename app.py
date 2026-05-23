"""
Norrin AI Act Compliance Assistant — Streamlit compliance console.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import html
import json
import re
import time
import uuid
from pathlib import Path

import streamlit as st

from src.config import MOCK_LLM, CORPUS_DIR
from src.preprocessing import process_uploaded_files, process_manual_description
from src.chunking import chunk_document
from src.vector_store import (
    add_chunks_to_uploaded,
    delete_session_chunks,
    get_corpus_collection,
)
from src.pipeline import run_assessment_pipeline
from src.citation_resolver import format_source_label


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

def _inject_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        :root {
            --bg: #f5f2ea;
            --card: #faf8f0;
            --card-white: #ffffff;
            --green: #00543f;
            --green-dark: #073b2e;
            --text: #102a24;
            --muted: #61736b;
            --border: #d8d1bf;
            --warn-bg: #fff4c2;
            --info-bg: #ddecf5;
        }

        html, body, .stApp, [data-testid="stAppViewContainer"],
        [data-testid="stAppViewContainer"] > section {
            background: var(--bg) !important;
            color: var(--text) !important;
            font-family: Inter, "Segoe UI", system-ui, sans-serif !important;
            font-size: 15px !important;
        }

        #MainMenu, footer, header[data-testid="stHeader"] {
            visibility: hidden; height: 0 !important;
        }

        .block-container {
            padding-top: 0.5rem;
            padding-bottom: 2rem;
            max-width: 1320px;
        }

        h1, h2, h3, h4 {
            font-family: Georgia, "Times New Roman", serif !important;
            color: var(--green-dark) !important;
            font-weight: 600 !important;
        }

        p, li, span, label, .stMarkdown, [data-testid="stMarkdownContainer"] p {
            color: var(--text) !important;
            line-height: 1.55 !important;
        }

        [data-testid="stCaptionContainer"] p, .stCaption {
            color: var(--muted) !important;
            font-size: 0.82rem !important;
        }

        [data-testid="stWidgetLabel"] p {
            color: var(--muted) !important;
            font-weight: 600 !important;
        }

        .stTextInput input, .stTextArea textarea,
        div[data-baseweb="select"] > div {
            background: #fff !important;
            color: var(--text) !important;
            border: 1px solid var(--border) !important;
        }

        .stButton > button {
            background: #fff !important;
            color: var(--text) !important;
            border: 1px solid var(--border) !important;
            font-weight: 500 !important;
        }
        .stButton > button[kind="primary"],
        button[kind="primary"] {
            background-color: #00543F !important;
            color: #FFFFFF !important;
            border: 1px solid #00543F !important;
            font-weight: 600 !important;
        }
        .stButton > button[kind="primary"]:hover {
            background-color: #004030 !important;
            border-color: #004030 !important;
        }
        .stButton > button[kind="primary"] p,
        .stButton > button[kind="primary"] span,
        .stButton > button[kind="primary"] div,
        .stButton > button[kind="primary"] [data-testid="stMarkdownContainer"] p {
            color: #FFFFFF !important;
        }

        div[data-testid="stMetric"] {
            background: var(--card-white) !important;
            border: 1px solid var(--border) !important;
            border-radius: 4px !important;
            padding: 0.6rem !important;
        }
        [data-testid="stMetricLabel"] p {
            color: var(--muted) !important;
            font-size: 0.7rem !important;
            font-weight: 600 !important;
            text-transform: uppercase !important;
        }
        [data-testid="stMetricValue"] {
            color: var(--green-dark) !important;
            font-family: Georgia, serif !important;
            font-size: 1.05rem !important;
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--card-white) !important;
            border-color: var(--border) !important;
            border-radius: 6px !important;
        }

        [data-testid="stFileUploader"] section[data-testid="stFileUploadDropzone"] {
            background: var(--card) !important;
            border: 2px dashed var(--border) !important;
            min-height: 120px;
        }

        .stProgress label, .stProgress p { color: var(--text) !important; }

        /* Top nav */
        .norrin-topnav {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.65rem 0 0.85rem;
            border-bottom: 1px solid var(--border);
            margin-bottom: 1rem;
            gap: 1rem;
            flex-wrap: wrap;
        }
        .norrin-brand {
            display: flex;
            align-items: center;
            gap: 0.55rem;
            min-width: 140px;
        }
        .norrin-logo {
            width: 32px; height: 32px;
            background: var(--green);
            color: #fff;
            display: flex; align-items: center; justify-content: center;
            font-family: Georgia, serif;
            font-weight: 700;
            font-size: 1rem;
            border-radius: 3px;
        }
        .norrin-brand-name {
            font-family: Georgia, serif;
            font-size: 1.15rem;
            font-weight: 600;
            color: var(--green-dark) !important;
        }
        .norrin-nav {
            display: flex;
            gap: 1.25rem;
            flex-wrap: wrap;
        }
        .norrin-nav a {
            color: var(--muted) !important;
            text-decoration: none;
            font-size: 0.88rem;
            font-weight: 500;
        }
        .norrin-nav a.active {
            color: var(--green-dark) !important;
            font-weight: 600;
            border-bottom: 2px solid var(--green);
            padding-bottom: 2px;
        }
        .norrin-nav-ref {
            color: var(--muted) !important;
            font-size: 0.72rem;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }

        /* Badges */
        .risk-badge {
            display: inline-block;
            padding: 0.2rem 0.55rem;
            border-radius: 3px;
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            border: 1px solid var(--border);
            margin-right: 0.5rem;
        }
        .risk-badge.high { background: #fde8e8; color: #9b2c2c; border-color: #f5c6c6; }
        .risk-badge.medium { background: var(--warn-bg); color: #7a5a00; border-color: #e6d08a; }
        .risk-badge.low { background: #e8f0ec; color: var(--green); border-color: #b8d4c8; }

        /* Risk hero */
        .risk-hero {
            border-radius: 6px;
            padding: 1.15rem 1.25rem;
            margin-bottom: 1rem;
            border: 2px solid var(--border);
        }
        .risk-hero.high { background: #fef5f5; border-color: #f5c6c6; }
        .risk-hero.medium { background: #fffbea; border-color: #e6d08a; }
        .risk-hero.low { background: #f0f7f4; border-color: #b8d4c8; }
        .risk-hero-kicker {
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--muted) !important;
            margin-bottom: 0.35rem;
        }
        .risk-hero-tier {
            font-family: Georgia, "Times New Roman", serif;
            font-size: 1.65rem;
            font-weight: 700;
            color: var(--green-dark) !important;
            line-height: 1.2;
            margin-bottom: 0.45rem;
        }
        .risk-hero-meta {
            font-size: 0.85rem;
            color: var(--muted) !important;
            margin-bottom: 0.65rem;
        }
        .risk-hero-explain {
            font-size: 0.92rem;
            color: var(--text) !important;
            line-height: 1.55;
            max-width: 920px;
        }

        .session-actions {
            background: var(--card-white);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 0.75rem 1rem;
            margin-bottom: 1rem;
        }
        .session-actions-title {
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--muted) !important;
            margin-bottom: 0.55rem;
        }

        /* Nav tabs */
        .nav-active-hint {
            font-size: 0.72rem;
            color: var(--green-dark) !important;
            font-weight: 600;
            text-align: center;
            margin-top: -0.35rem;
        }

        /* Dark context panel */
        .ctx-panel {
            background: var(--green-dark);
            color: #f4f7f5;
            border-radius: 6px;
            padding: 1rem 1.05rem;
            margin-bottom: 1rem;
        }
        .ctx-panel .ctx-title {
            font-size: 0.65rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: rgba(255,255,255,0.55);
            margin-bottom: 0.85rem;
            font-weight: 600;
        }
        .ctx-panel .ctx-row {
            margin-bottom: 0.65rem;
            padding-bottom: 0.55rem;
            border-bottom: 1px solid rgba(255,255,255,0.12);
        }
        .ctx-panel .ctx-row:last-child { border-bottom: none; margin-bottom: 0; }
        .ctx-panel .ctx-lbl {
            font-size: 0.62rem;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            color: rgba(255,255,255,0.5);
            margin-bottom: 0.15rem;
        }
        .ctx-panel .ctx-val {
            font-size: 0.88rem;
            color: #fff !important;
            line-height: 1.35;
            word-break: break-word;
        }

        /* Timeline */
        .timeline-wrap { margin-top: 0.25rem; }
        .tl-item {
            display: flex;
            gap: 0.65rem;
            margin-bottom: 1rem;
            position: relative;
        }
        .tl-dot-col {
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 14px;
            flex-shrink: 0;
        }
        .tl-dot {
            width: 10px; height: 10px;
            border-radius: 50%;
            background: var(--green);
            border: 2px solid var(--bg);
            margin-top: 0.25rem;
        }
        .tl-dot.warn { background: #b8860b; }
        .tl-line {
            width: 2px;
            flex-grow: 1;
            background: var(--border);
            margin-top: 4px;
            min-height: 24px;
        }
        .tl-body { flex: 1; }
        .tl-agent {
            font-family: Georgia, serif;
            font-size: 0.9rem;
            font-weight: 600;
            color: var(--green-dark) !important;
        }
        .tl-badge {
            display: inline-block;
            font-size: 0.58rem;
            font-weight: 700;
            letter-spacing: 0.05em;
            padding: 0.1rem 0.35rem;
            border-radius: 3px;
            margin-left: 0.35rem;
            vertical-align: middle;
        }
        .tl-badge.pass { background: #e8f0ec; color: var(--green); border: 1px solid #b8d4c8; }
        .tl-badge.revise { background: var(--warn-bg); color: #856404; border: 1px solid #e6d08a; }
        .tl-badge.done { background: #eef2f0; color: var(--green-dark); border: 1px solid var(--border); }
        .tl-detail {
            font-size: 0.8rem;
            color: var(--muted) !important;
            margin-top: 0.2rem;
            line-height: 1.4;
        }

        .section-rule {
            border: none;
            border-top: 1px solid var(--border);
            margin: 1.5rem 0 1rem;
        }

        .disclaimer-bar {
            background: var(--warn-bg);
            border: 1px solid #e6d08a;
            border-left: 4px solid #b8860b;
            padding: 0.6rem 0.85rem;
            margin-bottom: 1rem;
            font-size: 0.88rem;
            color: var(--text) !important;
            border-radius: 4px;
        }

        .gov-icon { color: var(--green); margin-right: 0.35rem; }

        [data-testid="stSidebar"] {
            background: var(--card-white) !important;
            border-right: 1px solid var(--border) !important;
        }
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] .stMarkdown,
        [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
            color: var(--text) !important;
            opacity: 1 !important;
        }
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            color: var(--green-dark) !important;
        }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.35rem;
            border-bottom: 1px solid var(--border);
        }
        .stTabs [data-baseweb="tab"] {
            color: var(--muted) !important;
            font-weight: 500 !important;
            font-size: 0.88rem !important;
            padding: 0.45rem 0.75rem !important;
        }
        .stTabs [aria-selected="true"] {
            color: var(--green-dark) !important;
            font-weight: 600 !important;
            border-bottom: 2px solid var(--green) !important;
        }
        .stTabs [data-baseweb="tab-panel"] {
            padding-top: 0.85rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _esc(text: str) -> str:
    return html.escape(str(text or ""))


def _kicker(text: str) -> None:
    st.markdown(
        f'<p style="margin:0 0 0.65rem;color:#61736b;font-size:0.72rem;'
        f'font-weight:600;letter-spacing:0.05em;text-transform:uppercase;">{text}</p>',
        unsafe_allow_html=True,
    )


def _section_heading(num: str, title: str) -> None:
    st.markdown(
        f'<p style="margin:0 0 0.5rem;color:#61736b;font-size:0.72rem;font-weight:600;'
        f'letter-spacing:0.05em;text-transform:uppercase;">{num} · {title}</p>',
        unsafe_allow_html=True,
    )


def _truncate(text: str, max_len: int = 80) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    cut = text[: max_len - 1].rsplit(" ", 1)[0]
    return (cut or text[: max_len - 1]) + "…"


def _display_title(session_metadata: dict) -> str:
    case = (session_metadata or {}).get("case_name") or ""
    if case.strip():
        return _truncate(case.strip(), 80)
    return "AI Use Case Assessment"


_CHUNK_REF_RE = re.compile(r"\s*\((?:corpus|uploaded)_[^)]+\)\s*")


def _clean_display_text(text: str) -> str:
    if not text:
        return ""
    cleaned = _CHUNK_REF_RE.sub(" ", str(text))
    return re.sub(r"\s{2,}", " ", cleaned).strip()


def _render_top_nav(*, show_export: bool = False, result: dict | None = None) -> None:
    active = st.session_state.get("active_page", "assessment")
    nav_items = [
        ("assessment", "Assessment Console"),
        ("library", "Regulatory Library"),
        ("audit", "Audit Logs"),
    ]

    nav_cols = st.columns([3, 5, 2])
    with nav_cols[0]:
        st.markdown(
            """
            <div class="norrin-brand" style="padding-top:0.15rem;">
                <div class="norrin-logo">N</div>
                <span class="norrin-brand-name">Norrin</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with nav_cols[1]:
        bcols = st.columns(3)
        for col, (page_key, label) in zip(bcols, nav_items):
            with col:
                is_active = active == page_key
                if st.button(
                    label,
                    key=f"nav_{page_key}",
                    type="primary" if is_active else "secondary",
                    use_container_width=True,
                ):
                    st.session_state["active_page"] = page_key
                    st.rerun()
    with nav_cols[2]:
        ref_col, btn_col = st.columns([1, 1])
        with ref_col:
            st.markdown(
                '<p class="norrin-nav-ref" style="margin:0.55rem 0 0;text-align:right;">REF · EU-AI-2024-V1</p>',
                unsafe_allow_html=True,
            )
        with btn_col:
            if show_export and result is not None:
                brief = {
                    "session_id": st.session_state.get("session_id"),
                    "presented": result.get("presented"),
                    "assessment": result.get("assessment"),
                    "critic": result.get("critic"),
                }
                st.download_button(
                    "Export Brief",
                    data=json.dumps(brief, indent=2, default=str),
                    file_name=f"norrin_brief_{st.session_state.get('session_id', 'export')}.json",
                    mime="application/json",
                    use_container_width=True,
                )
    st.markdown(
        '<div style="border-bottom:1px solid #d8d1bf;margin-bottom:1rem;"></div>',
        unsafe_allow_html=True,
    )


def _user_facing_source(card: dict) -> str:
    resolved = card.get("_resolved") or card
    label = format_source_label(resolved) if resolved else ""
    if label and "_chunk" not in label.lower():
        return label
    return card.get("source") or card.get("source_label") or "Source not available"


def _risk_badge_class(risk_label: str) -> str:
    lower = (risk_label or "").lower()
    if any(k in lower for k in ("prohibited", "high", "unacceptable")):
        return "high"
    if any(k in lower for k in ("limited", "unclear", "gpai")):
        return "medium"
    return "low"


def _render_risk_hero(
    *,
    risk_label: str,
    conf_val: str,
    critic_label: str,
    revision_triggered: bool,
    explanation: str,
) -> None:
    badge_cls = _risk_badge_class(risk_label)
    rev_note = " · Revised once" if revision_triggered else ""
    meta_line = f"Confidence: {conf_val} · Critic: {critic_label.lower()}{rev_note}"
    explain = _clean_display_text(explanation) or "See preliminary assessment below for full reasoning."
    st.markdown(
        f'<div class="risk-hero {badge_cls}">'
        f'<div class="risk-hero-kicker">Risk tier</div>'
        f'<div class="risk-hero-tier">{_esc(risk_label)}</div>'
        f'<div class="risk-hero-meta">{_esc(meta_line)}</div>'
        f'<div class="risk-hero-explain">{_esc(explain)}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_context_panel_dark(
    *,
    session_id: str,
    session_metadata: dict,
    processed_docs: list[dict],
    facts_section: dict | None,
) -> None:
    meta = session_metadata or {}
    files = [d["filename"] for d in processed_docs if not d.get("error")]
    sector = meta.get("sector_hint") or "—"
    deployment = meta.get("deployment_context") or meta.get("case_name") or "—"
    if len(str(deployment)) > 120:
        deployment = str(deployment)[:117] + "…"
    region = meta.get("region_eu_use") or "—"
    model_notes = meta.get("model_gpai_notes") or "—"
    for f in (facts_section or {}).get("facts") or []:
        if f.get("key") == "uses_gpai" and model_notes == "—":
            model_notes = f.get("value") or "—"
            break
    try:
        corpus_n = get_corpus_collection().count()
    except Exception:
        corpus_n = "—"

    rows = [
        ("Sector", sector),
        ("Deployment context", deployment),
        ("Organisation role", meta.get("org_role") or "—"),
        ("Region / EU use", region),
        ("Model / GPAI signal", model_notes),
        ("Source documents", f"{len(files)} file(s)"),
        ("Corpus indexed", f"{corpus_n} regulation chunks"),
        ("Session ID", session_id),
    ]
    row_html = "".join(
        f'<div class="ctx-row"><div class="ctx-lbl">{_esc(k)}</div>'
        f'<div class="ctx-val">{_esc(str(v))}</div></div>'
        for k, v in rows
    )
    st.markdown(
        f'<div class="ctx-panel"><div class="ctx-title">3 · System context</div>{row_html}</div>',
        unsafe_allow_html=True,
    )
    st.caption("Read-only summary. Edit in **Case metadata** (left sidebar) or re-run after updating **3 · Case context** on the intake page.")


def _apply_session_metadata(
    *,
    case_name: str,
    sector_hint: str,
    org_role: str,
    deployment_context: str,
    region_eu_use: str,
    model_gpai_notes: str,
) -> None:
    st.session_state["session_metadata"] = {
        "case_name": case_name.strip() or None,
        "sector_hint": sector_hint.strip() or None,
        "org_role": org_role or None,
        "deployment_context": deployment_context.strip() or None,
        "region_eu_use": region_eu_use.strip() or None,
        "model_gpai_notes": model_gpai_notes.strip() or None,
        **{
            k: v
            for k, v in (st.session_state.get("session_metadata") or {}).items()
            if k == "manual_use_case_description"
        },
    }


def _metadata_form_sidebar() -> bool:
    """Render sidebar metadata form. Returns True if saved."""
    meta = st.session_state.get("session_metadata") or {}
    with st.form("metadata_form_sidebar", clear_on_submit=False):
        case_name = st.text_input(
            "Use-case name",
            value=meta.get("case_name") or "",
            key="sidebar_meta_case_name",
        )
        sector_hint = st.text_input(
            "Sector hint",
            value=meta.get("sector_hint") or "",
            key="sidebar_meta_sector",
        )
        org_role = st.selectbox(
            "Organisation role / likely role",
            options=["", "provider", "deployer", "both", "unclear"],
            index=["", "provider", "deployer", "both", "unclear"].index(
                meta.get("org_role") or ""
            ),
            key="sidebar_meta_org_role",
        )
        deployment_context = st.text_area(
            "Deployment context",
            value=meta.get("deployment_context") or "",
            height=72,
            key="sidebar_meta_deployment",
        )
        region_eu_use = st.text_input(
            "Region / EU use",
            value=meta.get("region_eu_use") or "",
            placeholder="e.g. EU deployer, cross-border",
            key="sidebar_meta_region",
        )
        model_gpai_notes = st.text_area(
            "Model / GPAI notes",
            value=meta.get("model_gpai_notes") or "",
            height=72,
            placeholder="e.g. Llama-3.1, OpenAI API, embeddings model",
            key="sidebar_meta_gpai",
        )
        saved = st.form_submit_button("Save metadata", use_container_width=True, type="primary")
        if saved:
            _apply_session_metadata(
                case_name=case_name,
                sector_hint=sector_hint,
                org_role=org_role,
                deployment_context=deployment_context,
                region_eu_use=region_eu_use,
                model_gpai_notes=model_gpai_notes,
            )
            st.toast("Metadata saved")
            return True
    return False


def _sync_intake_metadata_from_widgets() -> None:
    """Copy intake page widget keys into session_metadata (called before Run assessment)."""
    _apply_session_metadata(
        case_name=st.session_state.get("intake_meta_case_name", ""),
        sector_hint=st.session_state.get("intake_meta_sector", ""),
        org_role=st.session_state.get("intake_meta_org_role", ""),
        deployment_context=st.session_state.get("intake_meta_deployment", ""),
        region_eu_use=st.session_state.get("intake_meta_region", ""),
        model_gpai_notes=st.session_state.get("intake_meta_gpai", ""),
    )


def _init_intake_metadata_widgets() -> None:
    meta = st.session_state.get("session_metadata") or {}
    defaults = {
        "intake_meta_case_name": meta.get("case_name") or "",
        "intake_meta_sector": meta.get("sector_hint") or "",
        "intake_meta_org_role": meta.get("org_role") or "",
        "intake_meta_deployment": meta.get("deployment_context") or "",
        "intake_meta_region": meta.get("region_eu_use") or "",
        "intake_meta_gpai": meta.get("model_gpai_notes") or "",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def _render_intake_metadata_card() -> None:
    """Case context on the intake page (feeds System context panel after run)."""
    _init_intake_metadata_widgets()
    with st.container(border=True):
        _section_heading("3", "Case context")
        st.markdown(
            '<p style="color:#61736b;font-size:0.82rem;margin:-0.25rem 0 0.75rem;">'
            "Optional · fills the System context panel on the report (sector, role, deployment).</p>",
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("Use-case name", key="intake_meta_case_name")
            st.text_input(
                "Sector",
                key="intake_meta_sector",
                placeholder="e.g. Workplace wellness, HR / employment",
            )
            st.selectbox(
                "Organisation role",
                options=["", "provider", "deployer", "both", "unclear"],
                key="intake_meta_org_role",
            )
        with c2:
            st.text_area(
                "Deployment context",
                key="intake_meta_deployment",
                height=88,
                placeholder="Where and how the system is used",
            )
            st.text_input(
                "Region / EU use",
                key="intake_meta_region",
                placeholder="e.g. EU workplace deployer",
            )
            st.text_input(
                "Model / GPAI notes",
                key="intake_meta_gpai",
                placeholder="e.g. proprietary model, third-party LLM",
            )
        if st.button("Save case context", key="intake_save_context"):
            _sync_intake_metadata_from_widgets()
            st.toast("Case context saved")
            st.rerun()


def _render_regulatory_library() -> None:
    st.markdown("## Regulatory Library")
    st.markdown(
        '<p style="color:#61736b;">Built-in corpus used for retrieval during assessment.</p>',
        unsafe_allow_html=True,
    )
    try:
        corpus_n = get_corpus_collection().count()
    except Exception:
        corpus_n = "—"

    m1, m2 = st.columns(2)
    m1.metric("Corpus indexed", f"{corpus_n} chunks")
    m2.metric("Legal sources loaded", str(len(list(CORPUS_DIR.glob("*")))))

    st.markdown("**Loaded legal sources**")
    sources = [
        ("EU AI Act (Regulation EU 2024/1689)", "EU_AI_Act.html"),
        (
            "Commission Guidelines — AI system definition (Art. 3)",
            "Commission_Guidelines_on_the_definition_of_an_artificial_intelligence_system_*.PDF",
        ),
        (
            "Commission Guidelines — Prohibited AI practices (Art. 5)",
            "Guidelines_on_prohibited_artificial_intelligence_practices_*.PDF",
        ),
    ]
    for title, fname in sources:
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(fname)

    st.info(
        "This corpus is embedded locally and retrieved by the Assessment Agent. "
        "Uploaded documents are indexed separately per session."
    )


def _render_audit_logs(result: dict | None) -> None:
    st.markdown("## Audit Logs")
    st.caption(f"Session · {st.session_state.get('session_id', '—')}")

    if result is None:
        st.warning("No assessment has been run in this session yet.")
        st.markdown("Run an assessment from **Assessment Console** to populate audit logs.")
        return

    critic = result.get("critic", {})
    meta = result.get("presented", {}).get("_meta", {})
    pipe_meta = result.get("_meta", {})
    revision_triggered = bool(meta.get("revision_triggered") or pipe_meta.get("revision_triggered"))
    critic_pass = critic.get("pass")

    c1, c2, c3 = st.columns(3)
    c1.metric("Critic verdict", "Pass" if critic_pass else "Revise" if critic_pass is False else "—")
    c2.metric("Revision", "Yes" if revision_triggered else "No")
    c3.metric("Pipeline stages", str(len(result.get("history") or [])))

    st.markdown("**Recent assessment stages**")
    history = result.get("history") or []
    if not history:
        st.caption("No pipeline history recorded.")
        return

    for h in history:
        stage = h.get("stage", "—")
        badge, detail = _timeline_summary(stage, h.get("output") or {})
        badge_cls = "pass" if badge == "PASS" else "revise" if badge == "REVISE" else "done"
        with st.container(border=True):
            st.markdown(
                f"**{_timeline_label(stage)}** "
                f'<span class="tl-badge {badge_cls}">{badge}</span>',
                unsafe_allow_html=True,
            )
            st.caption(detail)
            with st.expander(f"Raw output — {stage}"):
                st.json(h.get("output") or {}, expanded=False)


def _rerun_assessment(session_id: str) -> None:
    metadata = {
        **(st.session_state.get("session_metadata") or {}),
        "follow_up_answers": st.session_state.get("follow_up_answers") or [],
    }
    manual = metadata.get("manual_use_case_description")
    if manual:
        metadata["manual_use_case_description"] = manual
    with st.spinner("Re-running assessment…"):
        st.session_state["pipeline_result"] = run_assessment_pipeline(
            session_id, session_metadata=metadata
        )
    st.session_state["app_view"] = "results"
    st.session_state["active_page"] = "assessment"


def _render_session_actions(session_id: str, *, location: str = "main") -> None:
    """New case / Reassess controls for the results screen."""
    prefix = f"{location}_"
    can_reassess = bool(st.session_state.get("chunks")) and not st.session_state.get("is_running")

    container_ctx = st.container(border=True) if location == "main" else st.container()
    with container_ctx:
        if location == "main":
            st.markdown(
                '<p class="session-actions-title" style="margin:0 0 0.5rem;">Session actions</p>',
                unsafe_allow_html=True,
            )
            btn_new, btn_reassess, btn_hint = st.columns([1.1, 1.1, 3.8])
        else:
            btn_new, btn_reassess = st.columns(2)
            btn_hint = None
        with btn_new:
            if st.button(
                "↺ New case",
                use_container_width=True,
                key=f"{prefix}session_new_case",
                help="Clear this session and start a fresh assessment.",
            ):
                _reset_session()
                st.rerun()
        with btn_reassess:
            if st.button(
                "↻ Reassess",
                type="primary",
                use_container_width=True,
                disabled=not can_reassess,
                key=f"{prefix}session_reassess",
                help="Re-run the pipeline with the same documents and metadata.",
            ):
                _rerun_assessment(session_id)
                st.rerun()
        if btn_hint is not None:
            with btn_hint:
                st.markdown(
                    '<p style="margin:0.35rem 0 0;color:#61736b;font-size:0.82rem;line-height:1.45;">'
                    "<strong>New case</strong> clears this session and returns to upload. "
                    "<strong>Reassess</strong> re-runs Assessment → Critic → Presenter "
                    "using the same files and sidebar metadata.</p>",
                    unsafe_allow_html=True,
                )


def _render_agent_timeline(
    history: list[dict], revision_triggered: bool, *, compact: bool = False
) -> None:
    _section_heading("10", "Agent pipeline history")
    if revision_triggered:
        st.markdown(
            '<p style="font-size:0.82rem;color:#61736b;margin-bottom:0.75rem;">'
            "Critic triggered one revision pass.</p>",
            unsafe_allow_html=True,
        )

    if not history:
        st.caption("No pipeline history recorded.")
        return

    items_html: list[str] = []
    for idx, h in enumerate(history):
        stage = h["stage"]
        out = h["output"]
        agent = _timeline_label(stage)
        badge, detail = _timeline_summary(stage, out)
        badge_cls = "pass" if badge == "PASS" else "revise" if badge == "REVISE" else "done"
        dot_cls = "warn" if badge == "REVISE" else ""
        line_html = '<div class="tl-line"></div>' if idx < len(history) - 1 else ""
        plain_detail = detail.replace("**", "")
        items_html.append(
            f'<div class="tl-item">'
            f'<div class="tl-dot-col"><div class="tl-dot {dot_cls}"></div>{line_html}</div>'
            f'<div class="tl-body">'
            f'<span class="tl-agent">{_esc(agent)}</span>'
            f'<span class="tl-badge {badge_cls}">{badge}</span>'
            f'<div class="tl-detail">{_esc(plain_detail)}</div>'
            f"</div></div>"
        )

    st.markdown(f'<div class="timeline-wrap">{"".join(items_html)}</div>', unsafe_allow_html=True)

    if compact:
        st.caption("Open the **Trace** tab for full agent outputs.")
        return

    for h in history:
        with st.expander(f"Raw output — {h['stage']}", expanded=False):
            st.json(h["output"], expanded=False)


def _render_fact_card(fact: dict) -> None:
    labels = [_user_facing_source(r) for r in (fact.get("evidence_resolved") or [])]
    evidence = "; ".join(dict.fromkeys(l for l in labels if l and l != "—")) or "—"
    with st.container(border=True):
        st.markdown(
            f'<p style="margin:0;font-size:0.72rem;font-weight:600;color:#b8860b;'
            f'text-transform:uppercase;letter-spacing:0.04em;">{_esc(fact["label"])}</p>',
            unsafe_allow_html=True,
        )
        st.markdown(f"**{fact.get('value', '—')}**")
        st.caption(f"Confidence: {fact.get('confidence', '—')} · Source: {evidence}")


def _render_citation_card(card: dict, *, show_claim: bool = True) -> None:
    category = card.get("evidence_category_label") or card.get("evidence_category") or ""
    claim = card.get("claim") or ""
    source = _user_facing_source(card)
    ev_type = card.get("evidence_type") or "Unknown"
    excerpt = (card.get("excerpt") or "").strip()
    explanation = (card.get("relevance_explanation") or "").strip()
    layer = card.get("law_layer_label")
    topic = card.get("topic_label")

    with st.container(border=True):
        if category:
            st.caption(category.upper())
        if show_claim and claim:
            st.markdown(f"**Claim:** {claim}")
        st.markdown(f"**Source:** {source}")
        st.markdown(f"**Type:** {ev_type}")
        if layer:
            st.markdown(f"**Legal layer:** {layer}")
        if topic:
            st.markdown(f"**Topic:** {topic}")
        if excerpt:
            st.markdown(f'*"{excerpt}"*')
        elif show_claim:
            st.caption("Evidence excerpt not available.")
        if explanation:
            st.markdown(f"**Why this supports the claim:** {explanation}")
        full = (card.get("full_text") or (card.get("_resolved") or {}).get("full_text") or "").strip()
        if full:
            with st.expander(f"Full source text ({len(full.split())} words)"):
                st.text(full)
        resolved = card.get("_resolved") or {}
        chunk_id = resolved.get("chunk_id") or card.get("chunk_id") or ""
        if chunk_id:
            with st.expander("Debug — chunk ID"):
                st.code(chunk_id)
                st.caption(f"Resolver: {resolved.get('resolver', '—')}")


def _render_warning_cards(warnings: list[dict]) -> None:
    for w in warnings:
        sev = w.get("severity", "low")
        msg = w.get("message", "")
        bg = "#fde8e8" if sev == "high" else "#fff4c2" if sev == "medium" else "#ddecf5"
        st.markdown(
            f'<div style="background:{bg};border:1px solid #d8d1bf;padding:0.55rem 0.75rem;'
            f'border-radius:4px;margin:0.35rem 0;font-size:0.88rem;color:#102a24;">{_esc(msg)}</div>',
            unsafe_allow_html=True,
        )


def _render_tab_overview(
    *,
    summary_body: str,
    ai_label: str,
    risk_label: str,
    conf_val: str,
    risk_explanation: str,
    warnings: list[dict],
    sections: dict,
) -> None:
    st.markdown("**Use-case summary**")
    if summary_body:
        st.write(summary_body)
    else:
        st.caption("No summary available.")

    st.markdown("**Preliminary assessment snapshot**")
    st.markdown(f"- **AI system:** {ai_label}")
    st.markdown(f"- **Risk tier:** {risk_label}")
    st.markdown(f"- **Confidence:** {conf_val}")
    short_reason = _truncate(risk_explanation, 280)
    if short_reason:
        st.write(short_reason)

    if warnings:
        st.markdown("**Key warnings**")
        _render_warning_cards(warnings)

    miss_section = sections.get("missing_information", {})
    follow_ups = (miss_section.get("follow_up_questions") or [])[:3]
    if follow_ups:
        st.markdown("**Top follow-up questions**")
        for q in follow_ups:
            st.write(f"- {q}")

    gov_items = (sections.get("governance_observations", {}).get("items") or [])[:3]
    if gov_items:
        st.markdown("**Top governance notes**")
        for item in gov_items:
            with st.container(border=True):
                st.markdown(f"**{item['area_label']}**")
                st.caption(_truncate(item.get("observation") or "", 200))


def _render_tab_assessment(pa_section: dict, ai_label: str, risk_label: str, conf_val: str) -> None:
    if not pa_section:
        st.caption("No assessment produced.")
        return

    st.markdown("**Why this classification**")
    st.markdown(f"- **AI system:** {ai_label}")
    st.markdown(f"- **Risk tier:** {risk_label}")
    st.markdown(f"- **Confidence:** {conf_val}")

    if pa_section.get("ai_system", {}).get("reasoning"):
        st.markdown("**AI system definition**")
        st.write(_clean_display_text(pa_section["ai_system"]["reasoning"]))

    if pa_section.get("reasoning"):
        st.markdown("**Risk classification reasoning**")
        st.write(_clean_display_text(pa_section["reasoning"]))

    conf_block = pa_section.get("confidence") or {}
    conf_reason = conf_block.get("reasoning") or conf_block.get("explanation") or ""
    if conf_reason:
        st.markdown("**Confidence explanation**")
        st.write(_clean_display_text(conf_reason))

    resolved_cites = pa_section.get("legal_citations_resolved") or []
    if resolved_cites:
        st.markdown("**Legal basis**")
        for r in resolved_cites:
            _render_citation_card(
                {
                    "claim": "Legal basis for preliminary assessment",
                    "source": r.get("source") or r.get("source_label"),
                    "evidence_type": r.get("evidence_type"),
                    "excerpt": r.get("excerpt"),
                    "relevance_explanation": r.get("relevance_explanation"),
                    "law_layer_label": r.get("law_layer_label"),
                    "topic_label": r.get("topic_label"),
                    "_resolved": r,
                },
                show_claim=False,
            )


def _render_tab_governance(sections: dict) -> None:
    items = sections.get("governance_observations", {}).get("items", [])
    if not items:
        st.caption("No governance observations.")
        return
    for item in items:
        with st.container(border=True):
            st.markdown(
                f'<p style="margin:0 0 0.35rem;color:#102a24;font-weight:600;">'
                f'<span class="gov-icon">✓</span>{_esc(item["area_label"])}</p>',
                unsafe_allow_html=True,
            )
            st.write(item["observation"])
            resolved = item.get("citations_resolved") or []
            if resolved:
                labels = [_user_facing_source(r) for r in resolved]
                st.caption("Sources: " + " · ".join(dict.fromkeys(labels)))


def _render_tab_facts(facts_section: dict) -> None:
    st.markdown("**What the agent read from your documents**")
    facts = facts_section.get("facts", [])
    if not facts:
        st.caption("No facts extracted.")
        return
    for i in range(0, len(facts), 2):
        ca, cb = st.columns(2)
        with ca:
            _render_fact_card(facts[i])
        if i + 1 < len(facts):
            with cb:
                _render_fact_card(facts[i + 1])


def _render_tab_missing(session_id: str, sections: dict) -> None:
    miss_section = sections.get("missing_information", {})
    missing = miss_section.get("missing", [])
    follow_ups = miss_section.get("follow_up_questions", [])

    if missing:
        for m in missing:
            with st.container(border=True):
                st.markdown(f"**{m['topic']}**")
                if m.get("why_it_matters"):
                    st.caption(m["why_it_matters"])
                if m.get("suggested_question"):
                    st.write(f"_Suggested question:_ {m['suggested_question']}")
    else:
        st.caption("No gaps flagged.")

    if follow_ups:
        st.markdown("**Follow-up questions**")
        for q in follow_ups:
            st.write(f"- {q}")

    st.markdown("**Answer follow-up questions or add new information**")
    if st.session_state.get("clear_missing_follow_up"):
        st.session_state["missing_follow_up_input"] = ""
        st.session_state["clear_missing_follow_up"] = False

    st.text_area(
        "Follow-up input",
        height=100,
        placeholder="Add clarifications for the next assessment run…",
        label_visibility="collapsed",
        key="missing_follow_up_input",
    )
    follow_up_text = st.session_state.get("missing_follow_up_input", "")

    bc1, bc2 = st.columns(2)
    with bc1:
        if st.button("Update assessment", type="primary", use_container_width=True, key="tab_update_assessment"):
            if follow_up_text.strip():
                _apply_follow_up(session_id, follow_up_text.strip())
                st.rerun()
            else:
                st.toast("Add some text first.")
    with bc2:
        if st.button("Save as context only", use_container_width=True, key="tab_save_context"):
            if follow_up_text.strip():
                _store_follow_up_context(follow_up_text.strip())
                st.session_state["clear_missing_follow_up"] = True
                st.toast("Saved to session context.")
                st.rerun()

    if st.session_state.get("pending_follow_up_context"):
        st.markdown("**Added context (pending re-run)**")
        for i, ctx in enumerate(st.session_state["pending_follow_up_context"], start=1):
            st.caption(f"#{i}: {ctx[:180]}{'…' if len(ctx) > 180 else ''}")


def _render_tab_citations(sections: dict) -> None:
    cit = sections.get("citations", {})
    primary = cit.get("citation_cards") or cit.get("claims_table") or []
    additional = cit.get("additional_evidence") or []
    inference = cit.get("system_inference") or {}

    st.markdown("**System inference (conclusions, not direct quotes)**")
    st.caption(inference.get("note", ""))
    if inference.get("ai_system_reasoning"):
        st.markdown("*AI system conclusion:*")
        st.write(_clean_display_text(inference["ai_system_reasoning"]))
    if inference.get("risk_reasoning"):
        st.markdown("*Risk classification conclusion:*")
        st.write(_clean_display_text(inference["risk_reasoning"]))

    st.markdown("**Supported facts and regulatory references**")
    if primary:
        for row in primary:
            _render_citation_card(row)
    else:
        st.caption("No strong primary citations.")

    if additional:
        with st.expander(f"Additional evidence ({len(additional)} weaker matches)"):
            for row in additional:
                _render_citation_card(row)


def _render_tab_trace(result: dict, revision_triggered: bool) -> None:
    history = result.get("history") or []
    _render_agent_timeline(history, revision_triggered, compact=False)


def _store_follow_up_context(answer: str) -> None:
    st.session_state.setdefault("pending_follow_up_context", [])
    st.session_state["pending_follow_up_context"].append(answer.strip())
    st.session_state["follow_up_answers"].append(answer.strip())


def _apply_follow_up(session_id: str, answer: str) -> None:
    st.session_state["follow_up_answers"].append(answer.strip())
    st.session_state["clear_missing_follow_up"] = True
    st.session_state["app_view"] = "results"
    sample_dir = Path("data") / "uploaded" / session_id
    sample_dir.mkdir(parents=True, exist_ok=True)
    n = len(st.session_state["follow_up_answers"])
    follow_up_path = sample_dir / f"follow_up_{n}.md"
    follow_up_path.write_text(f"# Follow-up clarification\n\n{answer.strip()}\n", encoding="utf-8")
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
        "session_metadata", "follow_up_answers", "pending_follow_up_context",
        "is_running", "clear_missing_follow_up", "app_view", "missing_follow_up_input",
        "active_page",
    ):
        st.session_state.pop(k, None)


def _timeline_label(stage: str) -> str:
    return {
        "assessment_v1": "Assessment Agent",
        "critic_v1": "Critic Agent",
        "assessment_v2": "Assessment Agent — revision",
        "critic_v2": "Critic Agent — re-review",
        "presenter": "Presenter Agent",
    }.get(stage, stage)


def _timeline_summary(stage: str, out: dict) -> tuple[str, str]:
    if stage.startswith("assessment"):
        pa = out.get("preliminary_assessment", {})
        badge = "DONE" if stage == "assessment_v2" else "DONE"
        detail = (
            f"Classified risk tier as {pa.get('risk_tier', '—')} "
            f"(confidence: {pa.get('confidence', '—')})."
        )
        return badge, detail
    if stage.startswith("critic"):
        if out.get("pass"):
            return "PASS", "No further revisions requested."
        issues = len(out.get("issues") or [])
        detail = f"Flagged {issues} issue(s). Returned for revision."
        instr = out.get("revision_instruction") or ""
        if instr:
            detail += f" {instr[:140]}{'…' if len(instr) > 140 else ''}"
        return "REVISE", detail
    if stage == "presenter":
        return "DONE", f"Formatted report with {len(out.get('warnings') or [])} warning(s)."
    return "—", ""


def _file_size_label(uploaded_file) -> str:
    try:
        size = uploaded_file.size
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.0f} KB"
        return f"{size / (1024 * 1024):.1f} MB"
    except Exception:
        return ""


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
        "pending_follow_up_context": [],
        "is_running": False,
        "clear_missing_follow_up": False,
        "missing_follow_up_input": "",
        "app_view": "intake",
        "active_page": "assessment",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)
    if st.session_state.get("pipeline_result") is not None:
        st.session_state["app_view"] = "results"


_init_state()
session_id: str = st.session_state["session_id"]
app_view: str = st.session_state["app_view"]


# Sidebar — case metadata & session controls
with st.sidebar:
    st.markdown("### Case metadata")
    has_result = st.session_state.get("pipeline_result") is not None
    if has_result:
        st.caption("Edit context, then Save metadata or Reassess.")
        if _metadata_form_sidebar():
            st.rerun()
    else:
        st.caption("Fill **3 · Case context** on the main page before Run assessment.")
    if MOCK_LLM:
        st.caption("Demo mode — offline fixtures.")
    st.divider()
    st.markdown("**Session actions**")
    _render_session_actions(session_id, location="sidebar")
    st.caption(f"Session: `{session_id}`")


active_page: str = st.session_state.get("active_page", "assessment")

# Regulatory Library page
if active_page == "library":
    _render_top_nav(show_export=False)
    st.markdown(
        '<div class="disclaimer-bar"><strong>Decision-support tool only — not legal advice.</strong> '
        "Outputs are preliminary and require review by qualified counsel.</div>",
        unsafe_allow_html=True,
    )
    _render_regulatory_library()
    st.stop()

# Audit Logs page
if active_page == "audit":
    _render_top_nav(show_export=st.session_state.get("pipeline_result") is not None,
                    result=st.session_state.get("pipeline_result"))
    st.markdown(
        '<div class="disclaimer-bar"><strong>Decision-support tool only — not legal advice.</strong> '
        "Outputs are preliminary and require review by qualified counsel.</div>",
        unsafe_allow_html=True,
    )
    _render_audit_logs(st.session_state.get("pipeline_result"))
    st.stop()


# ---------------------------------------------------------------------------
# Assessment Console — Intake
# ---------------------------------------------------------------------------

if app_view == "intake":
    _render_top_nav(show_export=False)

    st.markdown(
        '<div class="disclaimer-bar"><strong>Decision-support tool only — not legal advice.</strong> '
        "Outputs are preliminary and require review by qualified counsel.</div>",
        unsafe_allow_html=True,
    )

    st.markdown("## Submit AI use case")
    st.markdown(
        '<p style="color:#61736b;margin-top:-0.5rem;">Upload documents and/or describe the use case for a preliminary EU AI Act assessment.</p>',
        unsafe_allow_html=True,
    )

    col_up, col_desc = st.columns(2, gap="large")

    with col_up:
        with st.container(border=True):
            _section_heading("1", "Upload documents")
            st.markdown(
                '<p style="color:#61736b;font-size:0.82rem;margin:-0.25rem 0 0.75rem;">'
                "PDF · DOCX · PPTX · HTML · CSV · TXT · MD</p>",
                unsafe_allow_html=True,
            )
            uploaded_files = st.file_uploader(
                "Upload documents",
                type=["pdf", "docx", "pptx", "html", "htm", "csv", "txt", "md"],
                accept_multiple_files=True,
                label_visibility="collapsed",
            )
            if uploaded_files:
                st.markdown("**Selected files**")
                for uf in uploaded_files:
                    st.markdown(
                        f'<div style="padding:0.35rem 0;border-bottom:1px solid #d8d1bf;'
                        f'font-size:0.88rem;color:#102a24;">'
                        f'<strong>{_esc(uf.name)}</strong> · {_file_size_label(uf)}</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No files selected yet.")

    with col_desc:
        with st.container(border=True):
            _section_heading("2", "Describe the use case")
            st.markdown(
                '<p style="color:#61736b;font-size:0.82rem;margin:-0.25rem 0 0.75rem;">'
                "No document? Describe your AI use case here manually.</p>",
                unsafe_allow_html=True,
            )
            manual_description = st.text_area(
                "Use-case description",
                height=150,
                placeholder=(
                    "Example: We use an AI tool to rank job applicants based on CVs. "
                    "Recruiters review the top candidates before interview decisions."
                ),
                label_visibility="collapsed",
            )
            st.markdown(
                '<p style="color:#61736b;font-size:0.78rem;margin-top:0.5rem;">'
                "You can run an assessment from this description alone, or together with uploaded documents.</p>",
                unsafe_allow_html=True,
            )
            has_files = bool(uploaded_files)
            has_manual = bool(manual_description.strip())
            run_disabled = (not has_files and not has_manual) or st.session_state["is_running"]
            run_label = "Run assessment" if not st.session_state["is_running"] else "Analysis running…"
            if not has_files and not has_manual:
                st.caption("Add at least one document or a use-case description to enable Run assessment.")

    _render_intake_metadata_card()

    has_files = bool(uploaded_files) if "uploaded_files" in dir() else False
    has_manual = bool(manual_description.strip()) if "manual_description" in dir() else False
    run_disabled = (not has_files and not has_manual) or st.session_state["is_running"]
    run_label = "Run assessment" if not st.session_state["is_running"] else "Analysis running…"

    _, run_col = st.columns([4, 1])
    with run_col:
        run_clicked = st.button(
            run_label,
            type="primary",
            disabled=run_disabled,
            use_container_width=True,
            key="run_assessment_main",
        )

    if run_clicked:
        _sync_intake_metadata_from_widgets()
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
            st.session_state["session_metadata"] = {
                **(st.session_state.get("session_metadata") or {}),
                "manual_use_case_description": manual_description.strip(),
            }
        result = run_assessment_pipeline(session_id, session_metadata=metadata)
        st.session_state["pipeline_result"] = result
        progress.progress(100, text=f"Done in {time.perf_counter() - t_start:.1f}s")
        st.session_state["is_running"] = False
        st.session_state["app_view"] = "results"
        st.rerun()

    st.stop()


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

result = st.session_state.get("pipeline_result")
if result is None:
    st.session_state["app_view"] = "intake"
    st.rerun()

_render_top_nav(show_export=True, result=result)

st.markdown(
    '<div class="disclaimer-bar"><strong>Decision-support tool only — not legal advice.</strong> '
    "Outputs are preliminary and require review by qualified counsel.</div>",
    unsafe_allow_html=True,
)

_render_session_actions(session_id, location="main")

presented = result.get("presented", {})
sections = presented.get("sections", {})
warnings = presented.get("warnings", [])
meta = presented.get("_meta", {})
pipe_meta = result.get("_meta", {})
critic = result.get("critic", {})
pa_section = sections.get("preliminary_assessment", {})
facts_section = sections.get("extracted_facts", {})

ai_label = pa_section.get("ai_system", {}).get("label", "—")
risk_label = pa_section.get("risk_tier", {}).get("label", "—")
conf_val = pa_section.get("confidence", {}).get("value", "—")
critic_pass = critic.get("pass")
critic_label = "Pass" if critic_pass else "Revise" if critic_pass is False else "—"
revision_triggered = bool(meta.get("revision_triggered") or pipe_meta.get("revision_triggered"))
status_label = f"Draft · {'v2' if revision_triggered else 'v1'}"
legal_count = len(pa_section.get("legal_citations_resolved") or pa_section.get("legal_citations") or [])

summary = sections.get("use_case_summary", {})
summary_body = (summary.get("body") or "").strip()
report_title = _display_title(st.session_state.get("session_metadata") or {})
risk_explanation = _clean_display_text(pa_section.get("reasoning") or "")

sector_hint = (st.session_state.get("session_metadata") or {}).get("sector_hint") or ""
meta_line = " · ".join(
    p for p in [
        sector_hint.upper() if sector_hint else "",
        f"CASE {session_id.upper()}",
    ] if p
)

main_col, side_col = st.columns([72, 28], gap="large")

with main_col:
    _render_risk_hero(
        risk_label=risk_label,
        conf_val=conf_val,
        critic_label=critic_label,
        revision_triggered=revision_triggered,
        explanation=risk_explanation,
    )
    st.markdown(
        f'<span style="color:#61736b;font-size:0.72rem;letter-spacing:0.04em;">{_esc(meta_line)}</span>',
        unsafe_allow_html=True,
    )
    st.markdown(f"## {_esc(report_title)}")
    if summary_body:
        st.markdown(
            f'<p style="color:#102a24;font-size:0.95rem;">{_esc(_truncate(summary_body, 320))}</p>',
            unsafe_allow_html=True,
        )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Risk tier", risk_label)
    m2.metric("Legal triggers", str(legal_count))
    m3.metric("Confidence", conf_val)
    m4.metric("Status", f"{critic_label} · {status_label}")

    tab_overview, tab_assessment, tab_governance, tab_facts, tab_missing, tab_citations, tab_trace = st.tabs(
        [
            "Overview",
            "Assessment",
            "Governance",
            "Facts",
            "Missing info",
            "Citations",
            "Trace",
        ]
    )

    with tab_overview:
        _render_tab_overview(
            summary_body=summary_body,
            ai_label=ai_label,
            risk_label=risk_label,
            conf_val=conf_val,
            risk_explanation=risk_explanation,
            warnings=warnings,
            sections=sections,
        )

    with tab_assessment:
        _render_tab_assessment(pa_section, ai_label, risk_label, conf_val)

    with tab_governance:
        _render_tab_governance(sections)

    with tab_facts:
        _render_tab_facts(facts_section)

    with tab_missing:
        _render_tab_missing(session_id, sections)

    with tab_citations:
        _render_tab_citations(sections)

    with tab_trace:
        _render_tab_trace(result, revision_triggered)

with side_col:
    _render_context_panel_dark(
        session_id=session_id,
        session_metadata=st.session_state.get("session_metadata") or {},
        processed_docs=st.session_state.get("processed_docs") or [],
        facts_section=facts_section,
    )
    st.markdown(
        '<p style="font-size:0.72rem;font-weight:600;color:#61736b;letter-spacing:0.05em;'
        'text-transform:uppercase;margin:0.85rem 0 0.45rem;">Quick actions</p>',
        unsafe_allow_html=True,
    )
    sc1, sc2 = st.columns(2)
    with sc1:
        if st.button("New case", use_container_width=True, key="side_new_case"):
            _reset_session()
            st.rerun()
    with sc2:
        can_reassess = bool(st.session_state.get("chunks")) and not st.session_state.get("is_running")
        if st.button(
            "Reassess",
            type="primary",
            use_container_width=True,
            disabled=not can_reassess,
            key="side_reassess",
        ):
            _rerun_assessment(session_id)
            st.rerun()
    _render_agent_timeline(result.get("history", []), revision_triggered, compact=True)

st.divider()
st.caption(presented.get("disclaimer", ""))
