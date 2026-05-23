# Codebase Status

Living document tracking the state of the Norrin AI Act Compliance Assistant codebase. Update on every major change.

**Last updated:** 2026-05-23 (core audit fixes + readable citation cards)

---

## 1. Build progress against the MVP plan

Reference: [`docs/mvp_plan.md`](./mvp_plan.md), section 10.

| # | Step | Status |
|---|---|---|
| 1 | Streamlit app shell | done (upload, disclaimer, analyze button — built into `app.py`) |
| 2 | MarkItDown file conversion (`preprocessing.py`) | done + tested |
| 3 | Chunking function (`chunking.py`) | done + tested |
| 4 | Chroma vector store + config (`vector_store.py`, `config.py`) | done + tested |
| 5 | Built-in AI Act corpus + `load_corpus_to_chroma()` | done (1,874 chunks loaded) |
| 6 | Retrieval functions (`retrieval.py`) | done + expanded for Article 3, Article 5, Annex III, Article 50, GPAI |
| 7 | Assessment Agent with structured JSON output | done + expanded Article 3 / prohibited-subtype / high-risk-domain fields |
| 8 | Critic Agent with pass/fail loop | done + citation ID validation in mock mode |
| 8b | **Pipeline orchestrator** (extension of plan) | done + baseline retrieval reused across Assessment and Critic |
| 9 | Presenter Agent | done + tested |
| 10 | Dashboard display (`app.py`) | done + launch-tested |
| 11 | Follow-up input + re-run | done (state-reset bug fixed in `app.py` "Missing info & follow-up" tab) |
| 12 | Demo cases + trigger tests | done (5 Markdown demo cases + `tests/expected_triggers.json` + `scripts/evaluate_triggers.py`) |

---

## 2. Files in the repository

### Entry point (repo root)

| File | Responsibility |
|---|---|
| `app.py` | Streamlit dashboard. Upload UI, optional metadata form, runs the full pipeline, renders 6 sections in tabs, shows agent history, supports follow-up answers that trigger a pipeline re-run. |

### Source code (`src/`)

| File | Responsibility | Key exports |
|---|---|---|
| `config.py` | Central config — paths, model names, chunk settings, retrieval context caps, MOCK_LLM flag, API keys (from env) | All constants used app-wide |
| `preprocessing.py` | Convert uploads (PDF/DOCX/PPTX/HTML/CSV/TXT/MD) → Markdown via MarkItDown | `process_uploaded_files`, `convert_file_to_markdown` |
| `chunking.py` | Paragraph/sentence-aware chunker with metadata + overlap | `chunk_text`, `chunk_document` |
| `vector_store.py` | Chroma client + collections (`uploaded_docs_collection`, `ai_act_corpus_collection`) + corpus loader | `add_chunks_to_uploaded`, `load_corpus_to_chroma`, `get_uploaded_collection`, `get_corpus_collection`, `delete_session_chunks` |
| `retrieval.py` | RAG layer: expanded standard queries for Article 3, Article 5, Annex III, Article 50, GPAI, role clarity, governance; dedup, source tags, capped combined context | `retrieve_uploaded_context`, `retrieve_ai_act_context`, `retrieve_combined_context`, `STANDARD_QUERIES` |
| `citation_resolver.py` | Resolves cited `chunk_id` values into human-readable citation cards using Chroma lookup, pipeline evidence cache, and chunk-ID fallbacks | `resolve_citations`, `resolve_citation`, `format_source_label` |
| `citation_relevance.py` | Scores claim-to-excerpt alignment, labels citation categories, and separates primary citations from weaker contextual evidence | `enrich_citation_row`, `build_system_inference` |
| `llm.py` | LLM provider abstraction (DeepSeek / OpenAI / Anthropic) + mock-mode switch | `call_llm`, `is_mock_mode` |
| `pipeline.py` | Multi-agent orchestrator: retrieve once → Assessment → Critic → (revise once if fail) → resolve cited chunks → Presenter | `run_assessment_pipeline` |

### Agents (`src/agents/`)

| File | Role | Architecture |
|---|---|---|
| `assessment_agent.py` | Produce a structured first-pass EU AI Act assessment from retrieved evidence | Hybrid ReAct: accepts pre-retrieved baseline evidence, can request extra evidence, includes Article 3 definition notes, definition exclusion, prohibited subtype, high-risk domain, transparency/GPAI notes |
| `critic_agent.py` | Quality gate; decide pass/fail and emit revision instruction | Single structured LLM call, no retrieval, 8-point checklist + mock-mode citation ID validation against retrieved evidence |
| `presenter_agent.py` | Format the reviewed assessment into 6 display-ready dashboard sections + warnings + disclaimer | Pure programmatic formatter; uses resolved citation cards for source-aware evidence display |

### Built-in corpus (`corpus/`)

| File | Source type | Chunks indexed |
|---|---|---|
| `EU_AI_Act.html` | Official regulation text (EUR-Lex) | 1,040 |
| `Commission_Guidelines_on_the_definition_of_an_*.PDF` | Official guidance | 67 |
| `Guidelines_on_prohibited_artificial_intelligence_*.PDF` | Official guidance | 767 |
| **Total** | | **1,874** |

Cached Markdown conversions live in `data/converted_markdown/_corpus/` and are re-used on subsequent runs.

### Scripts

| File | Purpose |
|---|---|
| `scripts/load_corpus.py` | One-shot loader. Run once with `python -m scripts.load_corpus`. Use `--force` to wipe and reload. |
| `scripts/evaluate_triggers.py` | Runs the 5 demo cases against `tests/expected_triggers.json` in mock mode and checks expected AI Act paths. |

### Demo cases and trigger tests

| Path | Purpose |
|---|---|
| `demo_cases/` | Five Markdown demo cases: HR screening, customer chatbot, workplace emotion detection, spam filter, and LLM report generator. |
| `tests/expected_triggers.json` | Expected risk directions, required legal-path terms, and follow-up topics for trigger evaluation. |

### Config / infra

| File | Purpose |
|---|---|
| `requirements.txt` | Pinned Python dependencies |
| `.env.example` | Template — copy to `.env` and fill keys |
| `.env` | Local secrets (git-ignored) |
| `.gitignore` | Standard Python ignores + runtime data folders |

### Documentation (`docs/`)

| File | Purpose |
|---|---|
| `mvp_plan.md` | Original MVP plan (architecture, file responsibilities, demo cases, build order) |
| `codebase_status.md` | This file — current build state |

---

## 3. Data flow currently working

```text
User document
   ↓ MarkItDown
Markdown (data/converted_markdown/{session_id}/)
   ↓ chunk_text
Chunks with metadata
   ↓ add_chunks_to_uploaded
Chroma uploaded_docs_collection (filtered by session_id)

Corpus files (corpus/*.pdf, *.html)
   ↓ load_corpus_to_chroma  (one-shot, cached)
Chroma ai_act_corpus_collection (1,874 chunks)

run_assessment_pipeline(session_id)
   ↓
   ├── retrieve_combined_context(STANDARD_QUERIES) → baseline evidence
   ├── assessment_agent(baseline evidence) → assessment_v1
   ├── critic_agent               → verdict_v1
   ├── (if fail) assessment_agent(baseline evidence) → assessment_v2  (revision)
   ├── (if fail) critic_agent     → verdict_v2
   ├── resolve_citations(all cited chunk IDs + evidence cache)
   └── presenter_agent(chunk_lookup) → display-ready sections + citation cards + warnings
   ↓
{ assessment, critic, presented, evidence_context, history[], _meta }
```

---

## 4. Mock mode vs real LLM

- `MOCK_LLM=true` (default in `.env`) → agents return pre-canned fixtures keyed to keyword signals. Full pipeline runs in ~12 s, zero API cost.
- `MOCK_LLM=false` → same code path, hits the configured provider (`LLM_PROVIDER=deepseek` by default) using the key in `.env`.

5 mock fixtures cover the 5 demo cases: HR screening, customer chatbot, workplace emotion detection, spam filter, GPAI report generator. The Assessment mock maps placeholder citations onto retrieved chunk IDs where available. The Critic uses deterministic heuristics that mirror real critic behavior (flags missing citations, invalid citation IDs, over-confident prohibited findings, missing required sections).

---

## 5. What's next

1. **Run trigger evaluation in a dependency-complete environment.** Use `python -m scripts.evaluate_triggers` after installing requirements and loading the corpus.
2. **Optional: real-LLM run.** Flip `MOCK_LLM=false` in `.env` and verify the agents produce sensible output against the actual DeepSeek API on each demo case.
3. **Optional: polish pass.** Improve UI styling, add export-to-report, add a portfolio comparison view, or add Finnish implementation context (bonus capabilities from the challenge brief).

---

## 6. Update protocol

When making a major change (new agent, new pipeline stage, new file in `src/`, dependency change, breaking API change), update this file in the same commit:

1. Bump the `Last updated` date at the top.
2. Update the relevant row in section 1 (Build progress).
3. Add/modify the entry in section 2 (Files).
4. If the data flow changed, update section 3.
5. Note breaking changes in a new "## Changelog" subsection if one becomes necessary.
