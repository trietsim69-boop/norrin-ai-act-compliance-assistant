# Norrin AI Act Compliance Assistant

Streamlit + Chroma + RAG + **multi-agent** MVP for preliminary **EU AI Act** analysis of one AI use case per session.

Upload documents (or describe a use case manually) → retrieve official legal corpus + your uploads → structured assessment with critic review → readable report with citations and follow-up questions.

**Decision-support only — not legal advice.**

---

## What it does

- Multi-document intake + optional manual description  
- Fact extraction and risk-tier classification (AI system definition, Annex III, Art. 5, Art. 50, GPAI signals)  
- Governance observations, missing-info gaps, and **support-labelled** citation cards (strong / moderate / weak / unsupported)  
- **Assessment → validate → Critic → (one revision) → Presenter** pipeline with visible agent trace  

---

## Architecture (quick view)

```text
User input → MarkItDown → chunking → Chroma → retrieval (scoped corpus)
    → Assessment Agent → validate citations → Critic → [revision]
    → Citation resolver → relevance scoring → Presenter → Streamlit dashboard
```

Details: [`docs/architecture.md`](docs/architecture.md) · Multi-agent design: [`docs/multi_agent_pipeline.md`](docs/multi_agent_pipeline.md)

---

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -m scripts.load_corpus
streamlit run app.py
```

Full setup (env vars, mock mode, ports): [`docs/setup_and_run.md`](docs/setup_and_run.md)

---

## Demo cases

Six sample use-case folders in [`demo_cases/`](demo_cases/) — HR screening, chatbot, workplace emotion detection, spam filter, LLM/GPAI tool, **predictive maintenance**.

Judge demo script: [`docs/demo_guide.md`](docs/demo_guide.md)  
Automated checks: [`docs/evaluation_and_trigger_tests.md`](docs/evaluation_and_trigger_tests.md)

---

## Documentation map

| Doc | Audience | Contents |
|-----|----------|----------|
| [`AGENTS.md`](AGENTS.md) | Judges, devs | Agent roles, schemas, pipeline orchestration |
| [`docs/mvp_plan.md`](docs/mvp_plan.md) | Product | Goals, scope, in/out of MVP |
| [`docs/architecture.md`](docs/architecture.md) | Devs | Full technical flow |
| [`docs/multi_agent_pipeline.md`](docs/multi_agent_pipeline.md) | **Judges** | Why multi-agent, revision loop, grounding |
| [`docs/citation_and_evidence.md`](docs/citation_and_evidence.md) | Judges, devs | Citation cards, evidence types, limits |
| [`docs/setup_and_run.md`](docs/setup_and_run.md) | Devs | Install, corpus, Streamlit, `.env` |
| [`docs/demo_guide.md`](docs/demo_guide.md) | Presenters | Live demo script |
| [`docs/evaluation_and_trigger_tests.md`](docs/evaluation_and_trigger_tests.md) | Devs | Trigger tests, expected behaviour |
| [`docs/codebase_status.md`](docs/codebase_status.md) | Team | Done / remaining / known issues |

---

## Current status

**Done:** preprocessing, corpus loading, scoped RAG retrieval, citation validation + relevance layer, three agents + presenter, Streamlit console, six demo cases, trigger tests (6/6 mock with corpus loaded), citation unit tests (13/13).

**Remaining:** real-LLM regression log, export formats, deployment packaging.

Live tracker: [`docs/codebase_status.md`](docs/codebase_status.md)

---

## Safety

Preliminary assessment only. EU AI Act interpretation is evolving. Citations depend on retrieval quality and programmatic validation — weak sources are downgraded, not shown as strong proof. Human expert review required before any compliance or deployment decision. Not production-ready.

---

## License

See [`LICENSE`](LICENSE).
