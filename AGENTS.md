# AGENTS.md

Guide for any agent — human or AI — working on the **Norrin AI Act Compliance Assistant**.

This file is intentionally split into two parts:
1. **For humans** — the skillset required to contribute productively to this codebase.
2. **For AI coding agents** — conventions, build/test commands, and rules to respect when editing.

Both audiences should also read [`docs/mvp_plan.md`](./docs/mvp_plan.md) (architecture) and [`docs/codebase_status.md`](./docs/codebase_status.md) (current state).

---

## Part 1 — Skillset required (for humans joining the project)

This project sits at the intersection of three domains. You don't need to be expert in all three, but the team collectively must cover them.

### A. EU AI Act — domain knowledge (essential)

You should be comfortable reading and reasoning about:
- **Article 3** — definition of an AI system; the "inference" test
- **Article 5** — prohibited practices, especially **5(1)(f) workplace emotion recognition** and 5(1)(a)/(b) manipulation
- **Article 6 + Annex III** — high-risk classification, all 8 high-risk domains (especially area 4 employment, area 5 essential services)
- **Article 50** — transparency obligations (chatbot disclosure, deepfakes, AI-generated content labelling)
- **Chapter V** — General-Purpose AI (GPAI) provider vs deployer obligations
- The **provider vs deployer** distinction (Chapter III roles)

Without this knowledge you cannot:
- Validate the agent's outputs
- Write meaningful mock fixtures
- Author useful demo cases
- Judge whether the system is producing legally-sane reasoning

Reference material lives in `corpus/` (the actual regulation + Commission guidelines).

### B. Retrieval-Augmented Generation (RAG) engineering

- **Chunking** strategies (size, overlap, boundary awareness) and their effect on retrieval quality
- **Embeddings** (we use SentenceTransformers `all-MiniLM-L6-v2` locally; OpenAI `text-embedding-3-small` if `EMBEDDING_PROVIDER=openai`)
- **Vector databases** — specifically Chroma (collections, metadata filters, distance metrics, persistent client)
- **Semantic search trade-offs** — when retrieval fails silently, when to re-query, when distance scores are misleading
- **Multi-collection patterns** — session-scoped vs global corpus, and how to keep them separate

### C. Multi-agent LLM orchestration

- **Prompt engineering** — system prompts as agent "personalities", structured JSON output, schema enforcement
- **Tool / function calling** patterns (OpenAI-compatible API, including DeepSeek)
- **Agent loops** — ReAct (Thought → Action → Observation), Critic loops, bounded iteration
- **Provider abstraction** — supporting multiple LLM backends (OpenAI, Anthropic, DeepSeek) behind one interface
- **Mock-mode discipline** — keeping the system runnable offline with fixture responses

### D. Python / Streamlit / packaging (supporting)

- Python 3.13+ idioms (type hints, `pathlib`, dataclasses optional)
- `python-dotenv` for env management
- **Streamlit** for the UI shell — `st.session_state`, file uploaders, expanders, sidebars
- `requirements.txt` discipline — pinned versions, minimal surface area
- `.gitignore` discipline — secrets and runtime data never committed

### E. Soft skills

- **Epistemic humility** — outputs must read as preliminary, never as final legal advice
- **Citation discipline** — every legal claim must trace back to a corpus chunk
- **Transparency over confidence** — flagging "I don't know" is more valuable than guessing

---

## Part 2 — Conventions for AI coding agents

If you are an AI coding assistant editing this repository, follow these rules.

### Project layout (canonical)

```text
norrin-ai-act-compliance-assistant/
├── app.py                         (Streamlit entry point — not built yet)
├── requirements.txt
├── .env.example                   (template; never commit a real .env)
├── AGENTS.md                      (this file)
├── README.md
├── corpus/                        (official EU AI Act + Commission guidelines)
├── data/                          (runtime; git-ignored)
│   ├── uploaded/{session_id}/
│   ├── converted_markdown/{session_id}/
│   ├── converted_markdown/_corpus/  (cached MarkItDown output for corpus files)
│   ├── vector_store/                (Chroma persistent DB)
│   └── outputs/
├── corpus/                        (3 official documents, ~1,874 chunks once loaded)
├── demo_cases/                    (sample documents per demo path)
├── docs/
│   ├── mvp_plan.md                (the master plan)
│   └── codebase_status.md         (living status; UPDATE on major changes)
├── scripts/
│   └── load_corpus.py             (one-shot corpus loader)
├── src/
│   ├── config.py                  (single source of truth for settings/paths)
│   ├── preprocessing.py           (MarkItDown)
│   ├── chunking.py
│   ├── vector_store.py            (Chroma)
│   ├── retrieval.py               (RAG layer)
│   ├── llm.py                     (provider abstraction + mock mode)
│   ├── pipeline.py                (multi-agent orchestrator)
│   └── agents/
│       ├── assessment_agent.py    (hybrid ReAct, structured JSON)
│       ├── critic_agent.py        (pass/fail + revision instruction)
│       └── presenter_agent.py     (not built yet — pure formatter)
└── tests/
    └── expected_triggers.json     (not built yet)
```

### Build / run commands

| Action | Command (PowerShell, from repo root) |
|---|---|
| Install dependencies | `pip install -r requirements.txt` |
| Load EU AI Act corpus into Chroma (one-shot) | `python -m scripts.load_corpus` |
| Force-reload corpus after editing the loader | `python -m scripts.load_corpus --force` |
| Run Streamlit UI (when built) | `streamlit run app.py` |
| Quick mock-mode pipeline check (when needed) | write a temp script under `scripts/`, run `python -m scripts.<name>`, then delete it |

### Environment

Read from `.env` via `src.config`. Never hard-code provider URLs, model names, or paths — add them to `src/config.py`.

| Env var | Purpose |
|---|---|
| `MOCK_LLM` | `true` runs all agents from fixtures (offline). `false` hits the real LLM. |
| `LLM_PROVIDER` | `deepseek` (default) / `openai` / `anthropic` |
| `LLM_MODEL` | provider-specific model name |
| `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | only required when `MOCK_LLM=false` |
| `EMBEDDING_PROVIDER` | `local` (default, no key) or `openai` |

### Coding rules

1. **No new top-level frameworks without discussion** — keep the stack to: Streamlit, MarkItDown, Chroma, OpenAI/Anthropic SDKs, SentenceTransformers, python-dotenv, pydantic. Do not introduce LangChain, LlamaIndex, etc.
2. **All paths and constants live in `src/config.py`.** Never hard-code paths in modules.
3. **Every agent must support mock mode.** Every `call_llm(...)` invocation must pass a `mock=...` fixture. Mock fixtures live inline at the bottom of each agent file.
4. **Agents return structured JSON, not free text.** Use `response_format="json"` and parse defensively.
5. **Agents receive only retrieved chunks, never the raw vector DB or Chroma client.** Retrieval is the boundary.
6. **Every legal claim cites a corpus `chunk_id`. Every fact cites an uploaded `chunk_id` (or is flagged as missing).**
7. **Outputs must never read as final legal advice.** Use qualified language; the disclaimer is always present.
8. **Never commit `.env`.** Confirm `git status` does not show it before any commit.
9. **Update `docs/codebase_status.md`** in the same commit as any major change (new agent, new pipeline stage, new file in `src/`, dependency change, breaking API change).
10. **Comments narrate intent, not behavior.** Avoid restating what the code does; explain non-obvious decisions only.

### Multi-agent design (must preserve)

The challenge is evaluated partly on multi-agent design. Do not collapse the agents into a single LLM call. The required properties are:

- **Distinct roles** — Assessment (reasoning), Critic (quality gate), Presenter (formatting only)
- **Structured intermediate outputs** — JSON dicts passed between stages
- **Autonomous decisions per agent** — risk path selection, citation gaps, pass/fail, revision instructions
- **A bounded revision loop** — exactly one revision pass when the critic fails the assessment
- **Visible history** — `pipeline.run_assessment_pipeline` returns a `history[]` with every stage, used in the UI for transparency

### Anti-patterns to avoid

- Embedding the full corpus in a prompt instead of retrieving chunks
- Giving any agent access to `get_uploaded_collection()` or `get_corpus_collection()` directly
- Returning prose where JSON is expected
- Adding a new dependency to bypass writing ~50 lines of glue code
- Hiding stack traces in `try/except: pass`
- Skipping `_meta` fields in returned dicts (they power the UI's transparency story)

### When in doubt

Default to: small, testable, mock-friendly, structured-JSON. Re-read `docs/mvp_plan.md` if you are unsure whether something belongs.
