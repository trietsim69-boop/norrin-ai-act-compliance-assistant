# Agent design — Norrin AI Act Compliance Assistant

This document explains **multi-agent roles** for judges and developers. Implementation: `src/agents/`, orchestrated by `src/pipeline.py`.

For the full pipeline narrative see [`docs/multi_agent_pipeline.md`](docs/multi_agent_pipeline.md).

---

## Pipeline orchestrator (`src/pipeline.py`)

**Role:** Coordinates stages; agents do not call each other directly.

**Flow:**

```text
retrieve_combined_context()
  → assessment_agent()           # v1
  → critic_agent()
  → [if fail] assessment_agent() # v2 (revision)
  → [if fail] critic_agent()     # v2
  → resolve_citations()
  → presenter_agent()
```

**Returns:** `{ assessment, critic, presented, history[], _meta }`

- `history[]` — one entry per stage (`assessment_v1`, `critic_v1`, optional v2, `presenter`)
- `_meta.revision_triggered` — whether critic forced one revision pass (`MAX_REVISIONS = 1`)

---

## Assessment Agent (`src/agents/assessment_agent.py`)

**Role:** Primary legal-technical reasoning from **retrieved evidence only**.

### Input

- `session_id` — namespaces uploaded chunks in Chroma  
- `session_metadata` — case name, sector, org role, deployment context, follow-up answers  
- Retrieved `uploaded_chunks` + `corpus_chunks` (via `retrieve_combined_context`)  
- **Revision mode:** `previous_assessment` + `revision_instruction` from Critic  

Agents never receive the raw Chroma client or full vector DB.

### Autonomous decisions

- Which uploaded facts matter vs boilerplate  
- Risk path to explore (employment, transparency, prohibited practices, GPAI, etc.)  
- Whether the system meets the AI Act definition (Art. 3)  
- Preliminary risk tier and confidence  
- Governance observations proportional to risk  
- Which `chunk_id` values cite each claim  
- What information is missing and which follow-up questions to suggest  

### Output schema (structured JSON)

Top-level keys:

| Key | Purpose |
|-----|---------|
| `use_case_summary` | Plain-language summary |
| `extracted_facts` | purpose, sector, affected persons, automation, oversight, uses_gpai, … each with `value`, `confidence`, `evidence[]` |
| `preliminary_assessment` | `ai_system`, `risk_tier`, `confidence`, `reasoning`, `legal_citations[]` |
| `governance_observations[]` | area, observation, citations |
| `missing_information` | gaps + follow-up questions |
| `needs_more_evidence` | optional ReAct loop — extra search queries |

Plus `_meta` (iterations, chunk counts, revision flag).

### When it asks for more evidence

Hybrid **ReAct** loop (max 2 iterations): if the model returns `needs_more_evidence` queries, the agent runs additional retrieval on uploaded + corpus collections, dedupes, and re-prompts — bounded to avoid runaway loops.

### Mock mode

`MOCK_LLM=true` → keyword-matched fixtures for five demo paths (offline demos).

---

## Critic Agent (`src/agents/critic_agent.py`)

**Role:** Quality gate — **does not rewrite the assessment**; pass/fail + revision instruction.

### Input

- Assessment JSON from Assessment Agent  
- Same `uploaded_chunks` + `corpus_chunks` the assessor saw  

### Checklist

1. Required sections present  
2. Citation support — legal claims cite corpus IDs; facts cite uploads or are flagged missing  
3. Evidence separation — uploads vs regulation/guidance  
4. Confidence calibration — low when facts are missing; high only with clear cited support  
5. Useful missing-info / follow-up questions  
6. Legal safety — qualified language, not final legal advice  
7. Source relevance — corpus cites match claimed risk category  
8. Internal contradictions  

### Pass/fail logic

- **`pass: true`** — well-grounded, cited, appropriately qualified  
- **`pass: false`** — issues listed with severity; **`revision_instruction`** — single concrete fix for Assessment Agent  
- **`missing_questions[]`** — expert questions for humans  

Pipeline runs **at most one** revision cycle when `pass=false` and instruction is non-empty.

### Mock mode

Deterministic heuristics (missing citations, overconfidence on high-risk claims, etc.).

---

## Presenter Agent (`src/agents/presenter_agent.py`)

**Role:** **Deterministic formatter** — converts assessment + critic + resolved citations into dashboard sections.

### Why no LLM

The MVP plan forbids new legal reasoning at presentation time. A programmatic formatter:

- Adds **no** new legal conclusions  
- Renders instantly (no API latency/cost)  
- Makes output reproducible for judges  

### Autonomous formatting decisions (non-legal)

- Risk tier labels and warning severity  
- Grouping governance items and fact cards  
- Primary vs additional citation tiers (via `citation_relevance.py`)  
- System-inference block separated from direct quotes  
- Standard disclaimer text  

### Output

`presented` dict: `sections` (summary, facts, assessment, governance, missing, citations), `warnings[]`, `disclaimer`, `_meta`.

---

## Citation resolver (`src/citation_resolver.py`) — **not an agent**

**Role:** Python utility — maps internal `chunk_id` strings to **human-readable evidence cards**.

### Resolution order

1. Chroma lookup (uploaded or corpus collection)  
2. Evidence cache (chunks already retrieved this session)  
3. Chunk-ID heuristic (parse `corpus_*` / `sess_*` patterns)  

### Output per chunk

`source`, `source_label`, `evidence_type`, `excerpt`, `full_text`, `law_layer_label`, `topic_label`, `section`, `found`, `resolver`.

Used by Presenter and Streamlit UI via `format_source_label()` — raw chunk IDs hidden from main view (debug expander only).

Details: [`docs/citation_and_evidence.md`](docs/citation_and_evidence.md)

---

## Human contributor conventions

Build commands, env vars, coding rules, and anti-patterns: see **Part 2** below (unchanged from project conventions).

### Project layout

```text
app.py                    Streamlit UI
src/pipeline.py           orchestrator
src/agents/               assessment, critic, presenter
src/retrieval.py          RAG boundary
src/citation_resolver.py  evidence cards
src/citation_relevance.py scoring + tiers
docs/                     architecture + judge docs
```

### Build / run

| Action | Command |
|--------|---------|
| Load corpus | `python -m scripts.load_corpus` |
| Run UI | `streamlit run app.py --server.port 8521` |
| Trigger tests | `python -m scripts.run_trigger_tests` |

See [`docs/setup_and_run.md`](docs/setup_and_run.md).

### Environment

| Var | Purpose |
|-----|---------|
| `MOCK_LLM` | `true` offline fixtures / `false` live API |
| `LLM_PROVIDER` | `deepseek` / `openai` / `anthropic` |
| `EMBEDDING_PROVIDER` | `local` / `openai` |

Never commit `.env`.

### Multi-agent rules (must preserve)

- Distinct Assessment / Critic / Presenter roles — do not collapse into one LLM call  
- Structured JSON between stages  
- Bounded revision: **exactly one** critic-triggered revision  
- Visible `history[]` for transparency  
- Update [`docs/codebase_status.md`](docs/codebase_status.md) on major changes  

### Anti-patterns

- Embedding full corpus in prompts instead of retrieving  
- Giving agents direct Chroma access  
- Presenter adding new legal reasoning via LLM  
- Hiding critic failures or skipping `_meta`  

---

## Further reading

- [`docs/multi_agent_pipeline.md`](docs/multi_agent_pipeline.md) — judge-focused pipeline narrative  
- [`docs/architecture.md`](docs/architecture.md) — system components  
- [`docs/mvp_plan.md`](docs/mvp_plan.md) — product scope  
