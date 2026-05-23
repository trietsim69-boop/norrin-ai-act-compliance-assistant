# Codebase Status

Living document tracking the state of the Norrin AI Act Compliance Assistant codebase. Update on every major change.

**Last updated:** 2026-05-23 (UI redesign, citation layer, demo evaluation harness)

---

## 1. Build progress against the MVP plan

Reference: [`docs/mvp_plan.md`](./mvp_plan.md), section 10.

| # | Step | Status |
|---|---|---|
| 1 | Streamlit app shell | **done** — upload, manual description, disclaimer, progress bar, intake/results split |
| 2 | MarkItDown file conversion (`preprocessing.py`) | done + tested |
| 3 | Chunking function (`chunking.py`) | done + tested |
| 4 | Chroma vector store + config (`vector_store.py`, `config.py`) | done + tested |
| 5 | Built-in AI Act corpus + `load_corpus_to_chroma()` | done (1,874 chunks when loaded) |
| 6 | Retrieval functions (`retrieval.py`) | done + tested (8 standard queries + metadata-targeted corpus pulls) |
| 7 | Assessment Agent with structured JSON output | done + tested (mock + real LLM) |
| 8 | Critic Agent with pass/fail loop | done + tested (mock + real LLM) |
| 8b | Pipeline orchestrator (`pipeline.py`) | done + tested |
| 9 | Presenter Agent | done + tested (programmatic formatter) |
| 10 | Dashboard display (`app.py`) | **done** — dark IBM Plex theme, overview cards, 6 tabs, citation cards, agent trace |
| 11 | Follow-up input + re-run | done — sidebar “Refine the assessment” after first run |
| 12 | Demo cases + trigger tests | done — `demo_cases/`, `tests/expected_triggers.json`, `src/evaluation.py`, `scripts/run_trigger_tests.py` |

**MVP steps 1–12 are complete.** Further work is polish (export, deployment, real-LLM regression runs).

---

## 2. Files in the repository

### Entry point (repo root)

| File | Responsibility |
|---|---|
| `app.py` | Streamlit dashboard: intake view (upload + manual text), results view (report tabs), sidebar case metadata + follow-up, runs full pipeline with progress stages, renders overview cards, citations, agent history |

### Source code (`src/`)

| File | Responsibility | Key exports |
|---|---|---|
| `config.py` | Central config — paths, model names, chunk settings, `MOCK_LLM`, API keys | All constants used app-wide |
| `preprocessing.py` | Convert uploads (PDF/DOCX/PPTX/HTML/CSV/TXT/MD) → Markdown via MarkItDown | `process_uploaded_files`, `process_manual_description` |
| `chunking.py` | Paragraph/sentence-aware chunker with metadata + overlap | `chunk_text`, `chunk_document` |
| `vector_store.py` | Chroma client, session-scoped uploads + global corpus collection, corpus loader | `add_chunks_to_uploaded`, `load_corpus_to_chroma`, `delete_session_chunks` |
| `corpus_metadata.py` | Law layer, topic, citation labels on corpus chunks; targeted retrieval inference | `enrich_corpus_chunk`, `infer_retrieval_targets`, `build_citation_label` |
| `retrieval.py` | RAG: 8 standard queries, dedup, metadata-filtered corpus pulls | `retrieve_combined_context`, `STANDARD_QUERIES` |
| `citation_resolver.py` | Resolve internal chunk IDs → human-readable citation cards | `resolve_citations`, `format_source_label` |
| `citation_relevance.py` | Claim↔excerpt relevance scoring, primary vs additional tier, system-inference block | `enrich_citation_row`, `build_system_inference` |
| `llm.py` | LLM abstraction (DeepSeek / OpenAI / Anthropic) + mock switch | `call_llm`, `is_mock_mode` |
| `pipeline.py` | Orchestrator: Assessment → Critic → (one revision) → citation resolve → Presenter | `run_assessment_pipeline` |
| `evaluation.py` | Trigger-based demo evaluation harness | `run_all_trigger_tests`, `run_trigger_test` |

### Agents (`src/agents/`)

| File | Role | Architecture |
|---|---|---|
| `assessment_agent.py` | Structured EU AI Act assessment from retrieved evidence | Hybrid ReAct: baseline retrieval → LLM JSON → optional `needs_more_evidence` loop (max 2 iterations) |
| `critic_agent.py` | Quality gate; pass/fail + revision instruction | Single structured LLM call, deterministic mock heuristics |
| `presenter_agent.py` | Format assessment into dashboard sections + citation cards | Pure programmatic — no LLM |

### Built-in corpus (`corpus/`)

| File | Source type | Chunks indexed |
|---|---|---|
| `EU_AI_Act.html` | Official regulation (EUR-Lex HTML) | 1,040 |
| `Commission_Guidelines_on_the_definition_of_an_*.PDF` | Official guidance | 67 |
| `Guidelines_on_prohibited_artificial_intelligence_*.PDF` | Official guidance | 767 |
| **Total** | | **1,874** |

Cached Markdown: `data/converted_markdown/_corpus/`

### Demo cases (`demo_cases/`)

Five folders, 14 sample Markdown files. See [`demo_cases/README.md`](../demo_cases/README.md).

### Tests

| File | Purpose |
|---|---|
| `tests/expected_triggers.json` | Expected risk direction, domain trigger, follow-up phrases per demo case |

### Scripts

| File | Purpose |
|---|---|
| `scripts/load_corpus.py` | `python -m scripts.load_corpus` (add `--force` to reload) |
| `scripts/run_trigger_tests.py` | `python -m scripts.run_trigger_tests` (add `--real-llm` for live API) |

### Config / infra

| File | Purpose |
|---|---|
| `requirements.txt` | Python dependencies (see file for stack breakdown) |
| `.env.example` | Env template — copy to `.env` |
| `.gitignore` | Python + `data/` runtime ignores |

### Documentation

| File | Purpose |
|---|---|
| `README.md` | Quick start, layout, env vars |
| `AGENTS.md` | Contributor skillset + agent coding rules |
| `docs/mvp_plan.md` | Original architecture plan |
| `docs/codebase_status.md` | This file |

---

## 3. Data flow

```text
User document / manual description
   ↓ MarkItDown (uploads only)
Markdown → chunk_document → add_chunks_to_uploaded
Chroma uploaded_docs_collection (session_id filter)

corpus/* → load_corpus_to_chroma (one-shot)
Chroma ai_act_corpus_collection (1,874 chunks)

run_assessment_pipeline(session_id)
   ├── retrieve_combined_context(STANDARD_QUERIES + metadata targets)
   ├── assessment_agent → assessment_v1
   ├── critic_agent → verdict_v1
   ├── (if fail) assessment_agent → assessment_v2
   ├── (if fail) critic_agent → verdict_v2
   ├── resolve_citations(cited chunk IDs + evidence cache)
   └── presenter_agent(chunk_lookup) → presented sections + warnings
   ↓
{ assessment, critic, presented, history[], _meta }
```

---

## 4. Streamlit UI (current)

- **Theme:** dark navy, IBM Plex Serif/Sans/Mono
- **Intake view:** file upload, manual description, run button with progress stages
- **Results view:** overview cards (AI system, risk tier, confidence, critic verdict), six tabs (facts, assessment, governance, missing info, citations, agent trace)
- **Sidebar:** case metadata form, follow-up refinement after first run, new assessment reset
- **Citations tab:** primary vs additional evidence, system-inference block separated from direct quotes

---

## 5. Mock mode vs real LLM

| Mode | Behaviour | Typical runtime |
|---|---|---|
| `MOCK_LLM=true` | Fixture responses keyed to document keywords | ~15–30 s per assessment |
| `MOCK_LLM=false` | Live DeepSeek/OpenAI/Anthropic API (2–6 calls + optional revision) | ~2–5+ min |

Five mock fixtures map to the five demo paths. Trigger tests: **5/5 pass** in mock mode (with corpus loaded).

**Shell override:** a `MOCK_LLM` variable set in PowerShell takes precedence over `.env` because `load_dotenv()` does not override existing env vars by default.

---

## 6. What's next (optional)

1. Real-LLM regression on all demo cases (`python -m scripts.run_trigger_tests --real-llm`)
2. UI polish — hide internal chunk IDs in user-facing prose, persistent progress on reruns, export report
3. Deployment — Streamlit Cloud or container; document production env setup

---

## 7. Update protocol

On major changes, update this file in the same commit:

1. Bump **Last updated** at the top
2. Section 1 — build progress rows
3. Section 2 — new/changed files
4. Section 3/4 — if data flow or UI changed
