# Norrin AI Act Compliance Assistant

A **Streamlit + Chroma + RAG + multi-agent** MVP for analyzing **one AI use case per session** against a built-in **EU AI Act and official Commission guidance** corpus. Users upload documents (or describe a system manually); the app retrieves relevant legal and document evidence, runs a structured assessment with a critic review loop, and presents a readable preliminary report with citations, governance notes, and follow-up questions.

**Decision-support only — not legal advice.**

---

## What the app does

- **Upload multiple use-case documents** (PDF, DOCX, PPTX, HTML, CSV, TXT, MD) or **describe the use case manually** when no file is available
- **Extract relevant facts** from uploads (purpose, sector, affected persons, automation, oversight, GPAI use, etc.)
- **Retrieve EU AI Act and official guidance** via semantic search over a pre-indexed corpus (~1,874 chunks)
- **Generate a preliminary AI Act assessment** (AI system definition, risk tier, confidence, reasoning, legal citations)
- **Run a Critic Agent** to review citation support, confidence, uncertainty, and unsupported claims
- **Revise once** if the critic fails the first assessment pass
- **Present a readable report** with tabbed sections, citation cards, and agent pipeline history
- **Surface missing information and follow-up questions** so humans can clarify gaps
- **Keep outputs qualified** — preliminary, transparent, and intended for expert review, not as final legal conclusions

---

## Architecture overview

```text
User documents + manual description
        ↓
MarkItDown preprocessing
        ↓
Chunking (session uploads + built-in corpus)
        ↓
Chroma vector stores
  · uploaded_docs_collection (per session)
  · ai_act_corpus_collection (global, loaded once)
        ↓
Retrieval (RAG) — combined uploaded + corpus context
        ↓
Assessment Agent
        ↓
Critic Agent
        ↓
Optional one revision (Assessment → Critic again)
        ↓
Citation resolver + relevance scoring
        ↓
Presenter Agent
        ↓
Streamlit regulatory console (dashboard)
```

Agents receive **retrieved chunks only**, not the full vector database. Every pipeline stage is recorded in `history[]` for transparency in the UI.

---

## Agents and supporting components

| Component | Role |
|---|---|
| **Assessment Agent** | Builds the EU AI Act assessment from retrieved evidence using hybrid ReAct-style reasoning; outputs structured JSON (facts, risk tier, governance, citations, missing info) |
| **Critic Agent** | Quality gate — checks citation support, confidence, uncertainty, and unsupported claims; returns pass/fail and revision instructions |
| **Presenter Agent** | **Deterministic formatter** (no LLM) — turns assessment JSON into dashboard sections, citation cards, warnings, and follow-up questions |
| **Citation resolver** | **Python utility, not an agent** — maps internal `chunk_id` values to human-readable evidence cards (source label, excerpt, legal layer, topic) |
| **Citation relevance** | Scores claim↔excerpt fit; separates primary vs additional evidence and system inference from direct quotes |

---

## Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ (tested on 3.13) |
| UI | Streamlit |
| Vector DB | ChromaDB (persistent local store) |
| Ingestion | MarkItDown (multi-format → Markdown) |
| Embeddings | SentenceTransformers (`all-MiniLM-L6-v2`) by default; optional OpenAI embeddings |
| LLM | Provider wrapper (DeepSeek default, OpenAI-compatible; also OpenAI / Anthropic) |
| Pattern | RAG + multi-agent orchestration |
| Source control | GitHub |

---

## Project structure

```text
app.py                    Streamlit entry point (intake, results, sidebar, UI helpers)
.streamlit/config.toml    Light theme (cream background, readable text)

src/
  preprocessing.py        MarkItDown conversion for uploads + manual descriptions
  chunking.py               Text chunking with overlap and metadata
  vector_store.py           Chroma collections, corpus loader, session cleanup
  retrieval.py              RAG queries (standard + targeted corpus pulls)
  citation_resolver.py      chunk_id → readable citation cards
  citation_relevance.py     Relevance scoring, primary/additional tiers
  pipeline.py               Assessment → Critic → (revision) → Presenter orchestration
  llm.py                    LLM provider abstraction + mock mode
  evaluation.py             Demo-case trigger test helpers
  agents/
    assessment_agent.py     Structured assessment (ReAct + JSON)
    critic_agent.py           Pass/fail + revision instruction
    presenter_agent.py        Report formatting (no LLM)

corpus/                   Official EU AI Act HTML + Commission guideline PDFs
demo_cases/               Sample use-case document sets for evaluation
scripts/
  load_corpus.py            One-shot corpus indexing into Chroma
  run_trigger_tests.py      Automated demo-case evaluation
docs/
  mvp_plan.md               Architecture plan
  codebase_status.md        Living build + UI status
tests/expected_triggers.json
data/                     Runtime uploads and vector store (git-ignored)
```

See [`docs/codebase_status.md`](docs/codebase_status.md) for detailed file inventory and UI behaviour.

---

## Setup

From the repository root (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy the environment template and edit locally:

```powershell
copy .env.example .env
```

**Never commit `.env`** — it may contain API keys. Only `.env.example` belongs in git.

---

## Environment variables

Example `.env` (placeholders only):

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_key_here
MOCK_LLM=true
EMBEDDING_PROVIDER=local
```

| Variable | Purpose |
|---|---|
| `MOCK_LLM` | `true` = offline fixture responses (development, demos, CI-style runs); `false` = live LLM API |
| `LLM_PROVIDER` | `deepseek` (default), `openai`, or `anthropic` |
| `LLM_MODEL` | Provider-specific model name |
| `EMBEDDING_PROVIDER` | `local` (default, no key) or `openai` |
| `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Required when `MOCK_LLM=false` for the chosen provider |

If `MOCK_LLM` is already set in your shell, it **overrides** `.env`. Example before a live run:

```powershell
$env:MOCK_LLM = "false"
```

---

## Loading the corpus

Run once after install (and again with `--force` after corpus or loader changes):

```powershell
python -m scripts.load_corpus
```

This converts the built-in legal sources in `corpus/`, chunks them, embeds them, and stores them in Chroma (`ai_act_corpus_collection`). Expect **~1,874 regulation and guidance chunks** when loaded successfully.

---

## Running the app

```powershell
streamlit run app.py
```

Recommended for local development (fixed port, less watcher overhead):

```powershell
streamlit run app.py --server.port 8521 --server.fileWatcherType none
```

Open the URL shown in the terminal (default http://localhost:8501 or your chosen port).

**Typical flow:** upload documents and/or enter a use-case description → **Run assessment** → review risk summary, tabs (Overview, Assessment, Governance, Facts, Missing info, Citations, Trace), and sidebar metadata. Use **New case** to reset or **Reassess** to re-run the pipeline on the same session inputs.

---

## Demo cases

The [`demo_cases/`](demo_cases/) folder contains sample document sets for five evaluation paths:

| Folder | Scenario | AI Act angle |
|---|---|---|
| `hr_screening/` | HR / recruitment screening | High-risk — Annex III employment |
| `customer_chatbot/` | Customer support chatbot | Limited risk / Article 50 transparency |
| `workplace_emotion_detection/` | Workplace emotion analytics | Prohibited practice — Article 5(1)(f) |
| `spam_filter/` | Email spam classification | Minimal risk |
| `llm_report_generator/` | Third-party LLM report tool | GPAI deployer obligations |

Run automated trigger checks (mock mode by default):

```powershell
python -m scripts.run_trigger_tests
python -m scripts.run_trigger_tests --case hr_screening --verbose
python -m scripts.run_trigger_tests --real-llm
```

Expected outcomes: [`tests/expected_triggers.json`](tests/expected_triggers.json). Details: [`demo_cases/README.md`](demo_cases/README.md).

---

## Safety and limitations

- **Not legal advice.** Outputs are preliminary classifications and governance prompts for human review.
- **Regulatory interpretation is evolving.** The EU AI Act and Commission guidance continue to develop; the app reflects retrieved sources at assessment time, not authoritative counsel.
- **Citations and uncertainty must be reviewed.** Chunk retrieval can be incomplete or misaligned; the Critic Agent reduces but does not eliminate error.
- **Confidence can be low** when uploads omit deployment context, oversight, or role (provider vs deployer).
- **Out-of-scope or adversarial inputs** should be treated cautiously; the tool is designed for good-faith compliance exploration, not as a bypass for prohibited use cases.
- **Not production-ready.** No warranty of accuracy, completeness, or fitness for regulatory filing.

---

## Evaluation alignment (Norrin hackathon)

| Criterion | How this project addresses it |
|---|---|
| **Content quality** | Structured sections: facts, assessment, governance, missing info, citations; qualified language throughout |
| **Regulatory grounding** | Built-in official corpus; legal claims tied to retrieved chunks and resolver-backed citation cards |
| **Multi-agent design** | Distinct Assessment, Critic, and Presenter roles; bounded revision loop; visible `history[]` |
| **UX** | Streamlit regulatory console: intake cards, risk hero, tabbed report, sidebar metadata, Audit Logs, Export Brief |
| **Technical implementation** | RAG over dual Chroma collections, MarkItDown pipeline, provider-abstracted LLM, mock mode for offline demo |
| **Transparency** | Agent trace, critic verdict, system-inference vs direct quotes, debug chunk IDs optional, disclaimer always shown |

---

## Current status

### Done

- Document preprocessing (MarkItDown) and chunking
- Chroma vector stores and one-shot corpus loading
- RAG retrieval (uploaded + corpus, targeted metadata pulls)
- Assessment Agent (structured JSON, ReAct-style evidence loop)
- Critic Agent (pass/fail, one revision cycle)
- Presenter Agent (deterministic report formatting)
- Citation resolver and relevance scoring
- Streamlit dashboard (intake, tabbed results, sidebar, nav pages, New case / Reassess)
- Citation cards with human-readable sources
- Demo cases and trigger-based evaluation harness (`5/5` in mock mode with corpus loaded)

### Remaining / possible improvements

- Richer follow-up reassessment workflow (deeper integration of user clarifications)
- Export report (PDF/Markdown beyond JSON Export Brief)
- More curated legal section boundaries (cleaner “full passage” context in citations)
- Stronger citation ranking and deduplication in the UI
- Real-LLM regression suite across all demo cases
- Deployment packaging (Streamlit Cloud / container)

---

## Further reading

- [`AGENTS.md`](AGENTS.md) — contributor conventions and agent design rules  
- [`docs/mvp_plan.md`](docs/mvp_plan.md) — original architecture plan  
- [`docs/codebase_status.md`](docs/codebase_status.md) — living technical and UI status  

## License

See [`LICENSE`](LICENSE).
