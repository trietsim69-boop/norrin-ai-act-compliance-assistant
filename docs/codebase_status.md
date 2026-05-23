# Codebase Status

Living document tracking the state of the Norrin AI Act Compliance Assistant codebase. Update on every major change.

**Last updated:** 2026-05-23 (demo cases + trigger-based evaluation harness)

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
| 6 | Retrieval functions (`retrieval.py`) | done + tested |
| 7 | Assessment Agent with structured JSON output | done + tested (mock mode) |
| 8 | Critic Agent with pass/fail loop | done + tested (mock mode) |
| 8b | **Pipeline orchestrator** (extension of plan) | done + tested |
| 9 | Presenter Agent | done + tested |
| 10 | Dashboard display (`app.py`) | done + launch-tested |
| 11 | Follow-up input + re-run | done (built into `app.py` "Missing info & follow-up" tab) |
| 12 | Demo cases + trigger tests | done (`demo_cases/`, `tests/expected_triggers.json`, `src/evaluation.py`, `scripts/run_trigger_tests.py`) |

---

## 2. Files in the repository

### Entry point (repo root)

| File | Responsibility |
|---|---|
| `app.py` | Streamlit dashboard. Upload UI, optional metadata form, runs the full pipeline, renders 6 sections in tabs, shows agent history, supports follow-up answers that trigger a pipeline re-run. |

### Source code (`src/`)

| File | Responsibility | Key exports |
|---|---|---|
| `config.py` | Central config — paths, model names, chunk settings, MOCK_LLM flag, API keys (from env) | All constants used app-wide |
| `preprocessing.py` | Convert uploads (PDF/DOCX/PPTX/HTML/CSV/TXT/MD) → Markdown via MarkItDown | `process_uploaded_files`, `convert_file_to_markdown` |
| `chunking.py` | Paragraph/sentence-aware chunker with metadata + overlap | `chunk_text`, `chunk_document` |
| `vector_store.py` | Chroma client + collections (`uploaded_docs_collection`, `ai_act_corpus_collection`) + corpus loader | `add_chunks_to_uploaded`, `load_corpus_to_chroma`, `get_uploaded_collection`, `get_corpus_collection`, `delete_session_chunks` |
| `retrieval.py` | RAG layer: 8 standard queries, dedup, distance-sorted results | `retrieve_uploaded_context`, `retrieve_ai_act_context`, `retrieve_combined_context`, `STANDARD_QUERIES` |
| `citation_resolver.py` | Resolve chunk_id → human-readable citation cards (Chroma lookup + evidence cache + chunk-ID heuristic) | `resolve_citations`, `resolve_citation`, `format_source_label` |
| `citation_relevance.py` | Score claim↔excerpt alignment, precise claim labels, relevance explanations, primary vs additional filter | `enrich_citation_row`, `build_system_inference` |
| `llm.py` | LLM provider abstraction (DeepSeek / OpenAI / Anthropic) + mock-mode switch | `call_llm`, `is_mock_mode` |
| `pipeline.py` | Multi-agent orchestrator: Assessment → Critic → (revise once if fail) | `run_assessment_pipeline` |
| `evaluation.py` | Trigger-based demo evaluation: ingest demo_cases, run pipeline, score against `tests/expected_triggers.json` | `run_all_trigger_tests`, `run_trigger_test`, `evaluate_pipeline_result` |

### Agents (`src/agents/`)

| File | Role | Architecture |
|---|---|---|
| `assessment_agent.py` | Produce a structured first-pass EU AI Act assessment from retrieved evidence | Hybrid ReAct: baseline retrieval → single LLM call → optional `needs_more_evidence` loop (capped at 2 iterations) |
| `critic_agent.py` | Quality gate; decide pass/fail and emit revision instruction | Single structured LLM call, no retrieval, 8-point checklist |
| `presenter_agent.py` | Format reviewed assessment into 6 dashboard sections; builds claims table + citation cards from resolved chunk metadata | Pure programmatic formatter — no LLM call |

### Built-in corpus (`corpus/`)

| File | Source type | Chunks indexed |
|---|---|---|
| `EU_AI_Act.html` | Official regulation text (EUR-Lex) | 1,040 |
| `Commission_Guidelines_on_the_definition_of_an_*.PDF` | Official guidance | 67 |
| `Guidelines_on_prohibited_artificial_intelligence_*.PDF` | Official guidance | 767 |
| **Total** | | **1,874** |

Cached Markdown conversions live in `data/converted_markdown/_corpus/` and are re-used on subsequent runs.

### Demo cases (`demo_cases/`)

Five folders with sample Markdown documents (2–3 files each) covering the MVP evaluation paths: HR screening, customer chatbot, workplace emotion detection, spam filter, LLM report generator. See [`demo_cases/README.md`](../demo_cases/README.md).

### Tests

| File | Purpose |
|---|---|
| `tests/expected_triggers.json` | Expected risk direction, domain trigger, and follow-up questions per demo case |

### Scripts

| File | Purpose |
|---|---|
| `scripts/load_corpus.py` | One-shot loader. Run once with `python -m scripts.load_corpus`. Use `--force` to wipe and reload. |
| `scripts/run_trigger_tests.py` | Run trigger-based evaluation on all demo cases (`python -m scripts.run_trigger_tests`). Defaults to `MOCK_LLM=true`; pass `--real-llm` for live API runs. |

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
   ├── assessment_agent           → assessment_v1
   ├── critic_agent               → verdict_v1
   ├── (if fail) assessment_agent → assessment_v2  (revision)
   ├── (if fail) critic_agent     → verdict_v2
   ├── resolve_citations(all cited chunk IDs + evidence cache)
   └── presenter_agent(chunk_lookup) → claims table, citation cards, warnings
   ↓
{ assessment, critic, presented, history[], _meta }
```

---

## 4. Mock mode vs real LLM

- `MOCK_LLM=true` (default in `.env`) → agents return pre-canned fixtures keyed to keyword signals. Full pipeline runs in ~12 s, zero API cost.
- `MOCK_LLM=false` → same code path, hits the configured provider (`LLM_PROVIDER=deepseek` by default) using the key in `.env`.

5 mock fixtures cover the 5 demo cases: HR screening, customer chatbot, workplace emotion detection, spam filter, GPAI report generator. The Critic uses deterministic heuristics that mirror real critic behavior (flags missing citations, over-confident prohibited findings, missing required sections).

---

## 5. What's next

1. **Optional: real-LLM run.** Flip `MOCK_LLM=false` in `.env` (or use `python -m scripts.run_trigger_tests --real-llm`) and verify agents against the live API on each demo case.
2. **Optional: polish pass.** Improve UI styling, add export-to-report, add a portfolio comparison view, or add Finnish implementation context (bonus capabilities from the challenge brief).

---

## 6. Update protocol

When making a major change (new agent, new pipeline stage, new file in `src/`, dependency change, breaking API change), update this file in the same commit:

1. Bump the `Last updated` date at the top.
2. Update the relevant row in section 1 (Build progress).
3. Add/modify the entry in section 2 (Files).
4. If the data flow changed, update section 3.
5. Note breaking changes in a new "## Changelog" subsection if one becomes necessary.
