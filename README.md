# Norrin AI Act Compliance Assistant

Multi-agent **EU AI Act** compliance assistant for the Norrin hackathon challenge. Upload use-case documents (or describe a system manually), run a structured assessment, and review a preliminary report with extracted facts, risk classification, governance notes, citations, and follow-up questions.

**Not legal advice.** Outputs are for structured human review only.

---

## Features

- **Document intake** — PDF, DOCX, PPTX, HTML, CSV, TXT, MD via MarkItDown, plus optional manual description
- **RAG over official corpus** — EU AI Act regulation + Commission guidelines (~1,874 indexed chunks after one-shot load)
- **Multi-agent pipeline** — Assessment (ReAct) → Critic (quality gate) → optional one revision → Presenter (formatter)
- **Streamlit dashboard** — dark theme, intake vs. results views, sidebar follow-up, six report tabs + agent trace
- **Mock mode** — full offline demo with fixture responses keyed to document keywords
- **Demo cases + trigger tests** — five evaluation paths with expected outcomes in `tests/expected_triggers.json`

---

## Quick start

### 1. Install

```powershell
cd norrin-ai-act-compliance-assistant
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure

```powershell
copy .env.example .env
```

Edit `.env` — at minimum set `MOCK_LLM=true` for offline demo, or `MOCK_LLM=false` plus `DEEPSEEK_API_KEY` (or another provider) for live LLM calls.

**Note:** If your shell has `MOCK_LLM` set globally, it overrides `.env`. In PowerShell before starting Streamlit:

```powershell
$env:MOCK_LLM = "false"   # or "true"
```

### 3. Load the EU AI Act corpus (once)

```powershell
python -m scripts.load_corpus
```

Use `--force` to wipe and reload after corpus or loader changes.

### 4. Run the UI

```powershell
streamlit run app.py --server.port 8521
```

Open http://localhost:8521 — upload documents or enter a description, then **Run assessment**.

For faster local dev (less file-watcher overhead):

```powershell
streamlit run app.py --server.port 8521 --server.fileWatcherType none
```

### 5. Run trigger tests (optional)

```powershell
python -m scripts.run_trigger_tests
python -m scripts.run_trigger_tests --case hr_screening --verbose
python -m scripts.run_trigger_tests --real-llm
```

Defaults to `MOCK_LLM=true`. Expect **5/5** passes in mock mode when the corpus is loaded.

---

## Project layout

```text
app.py                    Streamlit entry point
corpus/                   Official EU AI Act + Commission PDFs/HTML
demo_cases/               Sample documents per evaluation path
docs/                     MVP plan + living codebase status
scripts/
  load_corpus.py          One-shot corpus indexer
  run_trigger_tests.py    Demo-case evaluation harness
src/
  config.py               Paths, env, model settings
  preprocessing.py        MarkItDown conversion
  chunking.py             Chunking with overlap
  vector_store.py         Chroma collections + corpus loader
  corpus_metadata.py      Law-layer/topic metadata on corpus chunks
  retrieval.py            RAG queries (8 standard + targeted corpus pulls)
  citation_resolver.py    chunk_id → citation cards
  citation_relevance.py     Relevance scoring + system-inference separation
  llm.py                  Provider abstraction + mock mode
  pipeline.py             Assessment → Critic → Presenter orchestration
  evaluation.py           Trigger-test runner helpers
  agents/
    assessment_agent.py   Hybrid ReAct, structured JSON
    critic_agent.py       Pass/fail + revision instruction
    presenter_agent.py    Dashboard formatter (no LLM)
tests/expected_triggers.json
data/                     Runtime uploads, vector store (git-ignored)
```

See [`docs/codebase_status.md`](docs/codebase_status.md) for detailed build status and [`AGENTS.md`](AGENTS.md) for contributor conventions.

---

## Environment variables

| Variable | Purpose |
|---|---|
| `MOCK_LLM` | `true` = offline fixtures; `false` = real API |
| `LLM_PROVIDER` | `deepseek` (default), `openai`, `anthropic` |
| `LLM_MODEL` | Provider model name |
| `EMBEDDING_PROVIDER` | `local` (default) or `openai` |
| `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Required when `MOCK_LLM=false` |

---

## Demo cases

| Folder | Path tested |
|---|---|
| `hr_screening/` | High-risk — Annex III employment |
| `customer_chatbot/` | Limited risk / Article 50 transparency |
| `workplace_emotion_detection/` | Prohibited — Article 5(1)(f) |
| `spam_filter/` | Minimal risk |
| `llm_report_generator/` | GPAI deployer obligations |

Details: [`demo_cases/README.md`](demo_cases/README.md)

---

## License

See [`LICENSE`](LICENSE).
