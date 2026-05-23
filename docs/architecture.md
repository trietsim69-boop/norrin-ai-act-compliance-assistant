# System architecture

Technical overview of the Norrin AI Act Compliance Assistant. For agent-specific design see [`multi_agent_pipeline.md`](multi_agent_pipeline.md).

---

## End-to-end flow

```text
┌─────────────────────────────────────────────────────────────────┐
│  Streamlit UI (app.py)                                          │
│  intake · sidebar metadata · tabbed report · agent trace          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Preprocessing (src/preprocessing.py)                           │
│  MarkItDown: PDF/DOCX/PPTX/HTML/CSV/TXT/MD → Markdown           │
│  Manual description → synthetic Markdown doc                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Chunking (src/chunking.py)                                     │
│  ~800 chars, overlap 150, metadata: session_id, filename, …     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Chroma (src/vector_store.py) — persistent data/vector_store/   │
│  · uploaded_docs_collection  (filtered by session_id)           │
│  · ai_act_corpus_collection  (global, ~1,874 chunks)            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Retrieval (src/retrieval.py)                                   │
│  8 standard queries + metadata-targeted corpus pulls            │
│  → uploaded_chunks[] + corpus_chunks[]                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  LLM wrapper (src/llm.py) — DeepSeek / OpenAI / Anthropic       │
│  MOCK_LLM=true → fixtures (assessment + critic)                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
   Assessment Agent    Critic Agent      [optional revision]
         │                   │                   │
         └───────────────────┴───────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Citation resolver (src/citation_resolver.py)                   │
│  chunk_id → readable cards; relevance tiering (citation_relevance)│
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Presenter Agent (deterministic, no LLM)                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                    Streamlit dashboard
```

---

## Components

### Streamlit UI (`app.py`)

- **Session state:** `session_id`, `pipeline_result`, `session_metadata`, `app_view`, `active_page`  
- **Pages:** Assessment Console, Regulatory Library, Audit Logs  
- **Results layout:** 72/28 columns — tabs left, System Context + timeline right  
- All rendering helpers live in `app.py` (theme CSS in-file + `.streamlit/config.toml`)  

### Preprocessing & MarkItDown

- Converts heterogeneous uploads to Markdown under `data/converted_markdown/{session_id}/`  
- `process_manual_description()` creates a session Markdown file from textarea input  

### Chunking

- Paragraph/sentence-aware splits with overlap  
- Each chunk carries `chunk_id`, `session_id`, `source_type`, `document_type`  

### Chroma vector stores

| Collection | Scope | Loaded by |
|------------|-------|-----------|
| `uploaded_docs_collection` | Per-session user docs | Each upload / follow-up |
| `ai_act_corpus_collection` | Global regulation + guidance | `scripts/load_corpus.py` once |

Embeddings: SentenceTransformers `all-MiniLM-L6-v2` (default) or OpenAI `text-embedding-3-small`.

### Legal corpus (`corpus/`)

- `EU_AI_Act.html` — EUR-Lex regulation  
- Commission PDFs — AI system definition + prohibited practices guidelines  
- Enriched via `corpus_metadata.py` (law layer, topic, citation labels)  

### Retrieval

- **`retrieve_combined_context`** — entry point for pipeline  
- **`STANDARD_QUERIES`** — purpose, affected persons, sector, oversight, GPAI, employment, transparency, emotion recognition, …  
- **`infer_retrieval_targets`** — metadata-driven extra corpus pulls (e.g. Annex III employment)  
- Agents receive **only returned chunks** — retrieval is the security/relevance boundary  

### LLM wrapper

- Unified `call_llm()` with JSON mode, temperature, provider routing  
- Mock fixtures when `MOCK_LLM=true`  

### Agents

See [`multi_agent_pipeline.md`](multi_agent_pipeline.md) and [`../AGENTS.md`](../AGENTS.md).

### Citation layer

- **`citation_resolver.py`** — ID → card  
- **`citation_relevance.py`** — score, primary/additional tier, system-inference block  

See [`citation_and_evidence.md`](citation_and_evidence.md).

### Session state & data directories

```text
data/
  uploaded/{session_id}/       original + follow-up files
  converted_markdown/{session_id}/
  converted_markdown/_corpus/    cached corpus MarkItDown output
  vector_store/                Chroma persistence
```

`delete_session_chunks(session_id)` on New case reset.

---

## Configuration

Single source of truth: `src/config.py` (paths, models, chunk size, collection names, `MOCK_LLM`).

---

## Related docs

- Setup: [`setup_and_run.md`](setup_and_run.md)  
- Citations: [`citation_and_evidence.md`](citation_and_evidence.md)  
- Status: [`codebase_status.md`](codebase_status.md)  
