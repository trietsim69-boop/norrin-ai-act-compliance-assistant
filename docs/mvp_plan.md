# Norrin AI Act Assistant — Simple MVP Structure

> **Implementation status (2026-05-23):** MVP steps 1–12 are complete. For the live file list, UI behaviour, and run commands, see [`codebase_status.md`](./codebase_status.md) and [`README.md`](../README.md). This document remains the original architecture plan; sections below note where the built system differs (e.g. full EUR-Lex corpus files instead of simplified `.md` stubs, citation resolver layer, tabbed Streamlit console).

## 1. General Idea

Build a small app where the user uploads documents about **one AI use case**, then the system gives a **first-pass EU AI Act assessment**.

The MVP should handle:

- one AI use case per session
- multiple uploaded documents
- built-in EU AI Act reference corpus
- extracted facts
- preliminary risk assessment
- governance notes
- missing information
- citations and evidence separation
- simple follow-up questions

The main flow:

```text
User uploads documents
        ↓
MarkItDown converts files to Markdown
        ↓
Save Markdown to data/converted_markdown/
        ↓
Chunk Markdown text
        ↓
Create embeddings
        ↓
Store session chunks in Chroma (uploaded_docs_collection)
        ↓
Retrieval: fetch top relevant chunks from both
  - uploaded_docs_collection (session documents)
  - ai_act_corpus_collection (built-in corpus)
        ↓
Agent 1: Assessment Agent
  receives retrieved chunks only — not the full database
        ↓
Agent 2: Critic / Evaluator Agent
        ↓
  if pass = false → Agent 1 revises once
        ↓
Agent 3: Presenter Agent
        ↓
Final dashboard + follow-up questions
```

---

## 2. Recommended Tools

| Part | Use this for MVP | Why |
|---|---|---|
| UI | Streamlit | Fastest way to build a working demo |
| File conversion | MarkItDown | Converts PDF, DOCX, PPTX, HTML, CSV into Markdown in one tool; better coverage than PyMuPDF alone |
| Chunking | Custom Python function | Simple and controllable |
| Vector DB | Chroma | Easy local RAG setup, no separate server needed |
| Embeddings | OpenAI embeddings or SentenceTransformers | Turns chunks into vectors |
| LLM | Claude / GPT / available API | Agent reasoning |
| Agent framework | Simple Python functions | Avoid overengineering for hackathon |
| Data storage | Local files + JSON | Good enough for MVP |
| Evaluation | Trigger-based tests | Better than ML-style accuracy for this use case |

Recommended stack:

```text
Streamlit + MarkItDown + Chroma + OpenAI/Claude + simple Python agents
```

MarkItDown is chosen over PyMuPDF because it handles more file types with one library. Milvus can replace Chroma later if production scale is needed.

---

## 3. Main Architecture

```text
Frontend / App
  Streamlit app.py

Document Processing
  MarkItDown conversion
  Chunking
  Embedding
  Chroma storage (per-session collection)

Corpus (built-in, loaded once at startup)
  Chroma ai_act_corpus_collection

Retrieval Layer (runs before any agent)
  retrieve_uploaded_context(query, session_id)
  retrieve_ai_act_context(query)
  → both results combined → passed to Assessment Agent

Agents
  Assessment Agent    (receives retrieved chunks only)
  Critic / Evaluator Agent
  Presenter Agent     (formats only, adds no new legal reasoning)

Output
  Dashboard sections
  Citation panel
  Missing questions
  Follow-up input
```

---

## 4. Folder Structure

**As built (2026-05-23):**

```text
norrin-ai-act-compliance-assistant/
│
├── app.py                          Streamlit regulatory console (all UI)
├── .streamlit/config.toml          light theme overrides
├── requirements.txt
├── README.md
├── AGENTS.md
├── .env.example
│
├── data/                           runtime (git-ignored)
│   ├── uploaded/{session_id}/
│   ├── converted_markdown/{session_id}/
│   ├── converted_markdown/_corpus/
│   ├── vector_store/
│   └── outputs/
│
├── corpus/
│   ├── EU_AI_Act.html
│   ├── Commission_Guidelines_on_the_definition_of_an_*.PDF
│   └── Guidelines_on_prohibited_artificial_intelligence_*.PDF
│
├── src/
│   ├── config.py
│   ├── preprocessing.py
│   ├── chunking.py
│   ├── vector_store.py
│   ├── corpus_metadata.py
│   ├── retrieval.py
│   ├── citation_resolver.py
│   ├── citation_relevance.py
│   ├── llm.py
│   ├── pipeline.py
│   ├── evaluation.py
│   └── agents/
│       ├── assessment_agent.py
│       ├── critic_agent.py
│       └── presenter_agent.py
│
├── scripts/
│   ├── load_corpus.py
│   └── run_trigger_tests.py
│
├── demo_cases/
│   ├── hr_screening/
│   ├── customer_chatbot/
│   ├── spam_filter/
│   ├── workplace_emotion_detection/
│   └── llm_report_generator/
│
├── docs/
│   ├── mvp_plan.md
│   └── codebase_status.md
│
└── tests/
    └── expected_triggers.json
```

<details>
<summary>Original MVP sketch (superseded — kept for history)</summary>

```text
norrin-ai-act-assistant/
│
├── app.py
├── requirements.txt
├── README.md
├── .env.example
│
├── data/
│   ├── uploaded/
│   ├── converted_markdown/
│   ├── vector_store/
│   └── outputs/
│
├── corpus/
│   ├── ai_act_core.md
│   ├── ai_system_definition_guidance.md
│   └── prohibited_practices_guidance.md
│
├── src/
│   ├── config.py
│   ├── preprocessing.py
│   ├── chunking.py
│   ├── vector_store.py
│   ├── retrieval.py
│   ├── schemas.py
│   ├── evaluation.py
│   └── agents/
│       ├── assessment_agent.py
│       ├── critic_agent.py
│       └── presenter_agent.py
│
├── demo_cases/ …
└── tests/expected_triggers.json
```

</details>

---

## 5. File Responsibilities

### `app.py`

Main Streamlit regulatory console. **All UI logic lives in this file** (theme CSS, layout, render helpers); backend calls go through `src.pipeline` and related modules.

**Implemented (2026-05-23):**

- Top nav: Assessment Console · Regulatory Library · Audit Logs (`active_page`)
- Disclaimer bar (not legal advice)
- **Intake:** upload card + manual use-case description card; Run assessment with progress
- **Sidebar:** case metadata form; New case; Reassess
- **Results:** risk hero, summary metrics, session actions, 72/28 layout
- **Tabs:** Overview · Assessment · Governance · Facts · Missing info · Citations · Trace
- **Right column:** System Context (read-only), agent pipeline timeline, quick actions
- Follow-up in Missing info tab; Export Brief (JSON) in top nav
- Citation cards via `format_source_label()`; chunk IDs in debug expanders only

Session state uses `st.session_state`. A `session_id` (UUID) namespaces uploaded chunks in Chroma. Key keys: `session_id`, `pipeline_result`, `session_metadata`, `app_view` (`intake` | `results`), `active_page`.

---

### `src/config.py`

Central configuration for the app.

It should include:

- LLM provider and model name
- embedding model name
- Chroma persist directory (`data/vector_store/`)
- upload directory (`data/uploaded/`)
- converted markdown directory (`data/converted_markdown/`)
- corpus directory (`corpus/`)
- chunk size and overlap defaults
- max retrieval results (top-k)

All other modules import from `config.py` to avoid scattered hardcoded values.

---

### `src/preprocessing.py`

Handles file conversion using MarkItDown.

Main job:

```text
Uploaded file → MarkItDown → Markdown text → save to data/converted_markdown/
```

Example functions:

```python
convert_file_to_markdown(file_path) -> str
save_markdown(markdown_text, output_path)
process_uploaded_files(files, session_id) -> list[dict]
```

Returns a list of dicts with `filename`, `session_id`, `markdown_path`, and `document_type` (inferred from file name / content pattern).

---

### `src/chunking.py`

Splits Markdown into smaller chunks.

Example function:

```python
chunk_text(text, chunk_size=800, overlap=150) -> list[dict]
```

Each chunk should keep metadata:

```json
{
  "chunk_id": "session_abc123_doc1_chunk3",
  "session_id": "abc123",
  "filename": "hr_policy.pdf",
  "source_type": "uploaded_document",
  "document_type": "policy_document",
  "text": "...",
  "page": null
}
```

`session_id` is included in the chunk metadata and in the Chroma record so that retrieval can be filtered to the current session only.

---

### `src/vector_store.py`

Handles Chroma.

Main jobs:

- create or load the uploaded document collection (`uploaded_docs_collection`)
- create or load the built-in corpus collection (`ai_act_corpus_collection`)
- add session document chunks (keyed by `session_id`)
- search relevant chunks by query and optional filter

Use two collections:

```text
uploaded_docs_collection    → session documents, filtered by session_id
ai_act_corpus_collection    → built-in AI Act corpus, loaded once at startup
```

Include a `load_corpus_to_chroma()` function that:

1. Reads all files from `corpus/`
2. Chunks them with corpus-appropriate metadata
3. Embeds them
4. Stores them in `ai_act_corpus_collection`

This function runs once at app startup if the collection is empty. It does not re-run on every user session.

Corpus chunk metadata example:

```json
{
  "chunk_id": "ai_act_annex_iii_employment",
  "source_type": "regulation",
  "title": "EU AI Act",
  "section": "Annex III",
  "topic": "employment",
  "text": "..."
}
```

---

### `src/retrieval.py`

Handles RAG retrieval.

Example functions:

```python
retrieve_uploaded_context(query, session_id, top_k=6) -> list[dict]
retrieve_ai_act_context(query, top_k=6) -> list[dict]
retrieve_combined_context(queries, session_id) -> dict
```

`retrieve_combined_context` accepts a list of queries (e.g. purpose, affected persons, sector, oversight, GPAI usage) and returns both uploaded chunks and corpus chunks in a combined context object.

**Important:** Agents receive only the retrieved chunks returned by these functions. No agent receives the full vector database or a raw Chroma client.

---

### `src/agents/assessment_agent.py`

Main reasoning agent.

**What it receives:**

```json
{
  "session_metadata": {},
  "retrieved_uploaded_chunks": [],
  "retrieved_corpus_chunks": []
}
```

**What it does autonomously:**

1. Decides which uploaded-document facts are relevant to an AI Act analysis (ignores boilerplate)
2. Chooses which risk path to explore based on detected sector and purpose signals
3. Decides whether the described system appears to meet the AI Act definition of an AI system
4. Identifies possible risk category (prohibited, high, limited, minimal, unclear)
5. Decides whether GPAI or transparency obligations are likely relevant
6. Drafts governance observations proportional to the detected risk tier
7. Attaches evidence citations to every major claim
8. Identifies and flags facts that are missing or ambiguous

**Output shape:**

```json
{
  "use_case_summary": "...",
  "extracted_facts": {
    "purpose": {
      "value": "...",
      "confidence": "medium",
      "evidence": ["session_abc123_doc1_chunk3"]
    }
  },
  "preliminary_assessment": {
    "ai_system": "yes",
    "risk_tier": "high_risk_candidate",
    "confidence": "medium",
    "reasoning": "...",
    "legal_citations": ["ai_act_annex_iii_employment"]
  },
  "governance_observations": [],
  "missing_information": [],
  "citations": []
}
```

---

### `src/agents/critic_agent.py`

Quality gate agent.

**What it does autonomously:**

- Decides whether the assessment passes or requires revision
- Decides which specific claims lack sufficient citation support
- Decides whether the confidence level is too high for the available evidence
- Decides what follow-up questions to generate based on what is missing
- Triggers one revision loop if `pass = false`

**Evaluation checklist:**

| Test | Success condition |
|---|---|
| Required sections | Summary, facts, assessment, governance, missing info, citations are present |
| Citation support | Major risk and legal claims have citations |
| Evidence separation | Uploaded facts and legal references are clearly separated |
| Confidence control | Confidence is lowered when key facts are missing |
| Missing information | Useful follow-up questions are generated |
| Legal safety | Output avoids sounding like final legal advice |
| Source relevance | Retrieved AI Act references match the use case |
| Contradictions | Conflicting facts are flagged |

**Output shape:**

```json
{
  "pass": false,
  "issues": [
    "Human oversight is unclear",
    "High-risk classification needs softer wording"
  ],
  "revision_instruction": "Lower confidence and ask whether the AI output affects final decisions.",
  "missing_questions": [
    "Can a human override the AI output?",
    "Does the system make final decisions or only recommendations?"
  ]
}
```

If `pass = false`, the revision instruction is sent back to the Assessment Agent **once only**.

---

### `src/agents/presenter_agent.py`

Formats the final reviewed result into a clean dashboard/report.

**Important constraint:** The Presenter Agent does not introduce new legal reasoning. It only formats the content it receives from the Assessment Agent and the Critic's missing questions. If it cannot format something cleanly, it surfaces it as-is rather than rewriting it.

**Final sections:**

1. Use-case summary
2. Extracted facts
3. Preliminary EU AI Act assessment
4. Governance observations
5. Missing information and follow-up questions
6. Citations and evidence separation

---

## 6. Built-in Corpus Structure

**As built:** The repo ships the **full official sources** in `corpus/` (not simplified Markdown stubs):

| File | Role |
|---|---|
| `EU_AI_Act.html` | EUR-Lex regulation text |
| `Commission_Guidelines_on_the_definition_of_an_*.PDF` | Art. 3 AI system definition guidance |
| `Guidelines_on_prohibited_artificial_intelligence_*.PDF` | Art. 5 prohibited practices guidance |

`scripts/load_corpus.py` converts, chunks, enriches metadata via `corpus_metadata.py`, and loads **~1,874 chunks** into `ai_act_corpus_collection`.

Label every corpus chunk with `source_type: regulation` or `source_type: official_guidance` to support evidence separation in the output.

<details>
<summary>Original MVP sketch (curated markdown stubs — not used)</summary>

In `corpus/ai_act_core.md`, include a simplified curated version of:

- AI system definition (Article 3)
- Prohibited practices (Article 5)
- High-risk classification criteria (Article 6)
- Annex III high-risk areas (all eight domains)
- Transparency obligations (Article 50)
- GPAI obligations (Chapter V)

Separate stub files for Commission definition and prohibited-practices guidelines were planned instead of full PDFs/HTML.

</details>

---

## 7. Data Flow

```text
1. User uploads documents in Streamlit (session_id created, stored in st.session_state)

2. MarkItDown converts each file to Markdown

3. Markdown files are saved to:
   data/converted_markdown/{session_id}/

4. Markdown text is chunked (chunk_size=800, overlap=150)

5. Chunks are embedded and stored in Chroma uploaded_docs_collection
   filtered by session_id

6. Retrieval layer runs multiple queries against both collections:
   - What is the AI system purpose?
   - Who are affected persons?
   - Does this relate to employment or worker management?
   - Does this involve chatbot transparency?
   - Does this involve emotion recognition?
   - Is a third-party LLM or GPAI model used?
   Returns: retrieved_uploaded_chunks + retrieved_corpus_chunks

7. Assessment Agent receives only the retrieved chunks
   Drafts assessment with extracted facts, risk classification, governance, citations

8. Critic Agent receives assessment output + retrieved evidence
   Checks all criteria
   If pass = false: sends revision_instruction back to Assessment Agent (once only)

9. Assessment Agent revises if instructed

10. Citation resolver maps chunk IDs → readable citation cards; relevance layer tiers primary vs additional evidence

11. Presenter Agent formats final dashboard from reviewed output (no LLM)

12. User reads tabbed dashboard; can answer missing-information questions or Reassess

13. If user provides new information:
    - answer is indexed as follow-up document chunks
    - Assessment → Critic → Presenter re-run with updated context
    - Updated dashboard is shown
```

---

## 8. Demo Cases

Prepare five demo cases. Each case tests a different AI Act reasoning path.

### Demo 1 — HR Candidate Screening

Expected:

```text
Risk direction: high-risk candidate
Reason: employment / worker management (Annex III)
Missing questions: human oversight, final decision impact, provider/deployer role
```

Documents to prepare:

- product description of AI ranking candidates
- internal HR process note
- policy note on human review

---

### Demo 2 — Customer Support Chatbot

Expected:

```text
Risk direction: limited risk / transparency
Reason: chatbot interacting with humans (Article 50)
Possible GPAI issue if using third-party LLM
```

Documents to prepare:

- chatbot product description
- technical overview mentioning LLM use
- transparency notice draft

---

### Demo 3 — Workplace Emotion Detection

Expected:

```text
Risk direction: prohibited / unacceptable-risk signal
Reason: emotion recognition in workplace (Article 5)
Missing questions: what exactly is inferred, deployment context, exceptions
```

Documents to prepare:

- vendor pitch describing mood/emotion analytics
- workplace deployment note
- technical overview mentioning facial/emotion inference

---

### Demo 4 — Email Spam Filter

Expected:

```text
Risk direction: minimal risk
Reason: narrow filtering task, no decision impact on individuals
Governance note: minimal regulatory requirements; still mention good practice
```

Documents to prepare:

- product description of spam filtering function
- short technical overview

This case provides a "minimal risk" contrast and shows the system does not overclassify.

---

### Demo 5 — LLM Report Generator (internal tool)

Expected:

```text
Risk direction: GPAI-related obligations / responsibility chain
Reason: deploys a third-party GPAI model; deployer has compliance responsibilities
Missing questions: provider compliance documentation, role of human review
```

Documents to prepare:

- product brief describing internal report generation with GPT API
- internal policy on use

This case shows the GPAI path and responsibility chain reasoning.

---

## 9. Simple Evaluation

Use **trigger-based evaluation**.

The system is tested on whether known use cases trigger the expected AI Act reasoning path.

Example `tests/expected_triggers.json`:

```json
[
  {
    "case_name": "HR candidate screening",
    "expected_trigger": "employment",
    "expected_risk_direction": "high_risk",
    "must_ask_about": ["human oversight", "decision impact", "provider/deployer role"]
  },
  {
    "case_name": "Customer support chatbot",
    "expected_trigger": "chatbot",
    "expected_risk_direction": "limited_risk",
    "must_ask_about": ["transparency", "GPAI use"]
  },
  {
    "case_name": "Workplace emotion detection",
    "expected_trigger": "emotion recognition workplace",
    "expected_risk_direction": "prohibited_or_unacceptable",
    "must_ask_about": ["deployment context", "what is inferred"]
  },
  {
    "case_name": "Email spam filter",
    "expected_trigger": "narrow filtering",
    "expected_risk_direction": "minimal_risk",
    "must_ask_about": []
  },
  {
    "case_name": "LLM report generator",
    "expected_trigger": "GPAI third-party",
    "expected_risk_direction": "gpai_obligations",
    "must_ask_about": ["provider compliance", "human review"]
  }
]
```

For each case, check:

1. Did the system detect the correct domain?
2. Did it retrieve relevant AI Act references?
3. Did it produce the expected risk direction?
4. Did it cite major claims?
5. Did it avoid overconfident legal conclusions?
6. Did it ask useful missing-information questions?
7. Did the Critic Agent catch weak evidence?

This is more useful than ML-style accuracy because the system is not training a classifier. It is checking whether the right AI Act reasoning path is triggered.

---

## 10. MVP Build Order

```text
1.  Streamlit app shell (upload UI, disclaimer, analyze button, empty result sections)  ✓
2.  MarkItDown file conversion (preprocessing.py)  ✓
3.  Chunking function (chunking.py)  ✓
4.  Chroma vector store setup (vector_store.py, config.py)  ✓
5.  Built-in AI Act corpus → load_corpus_to_chroma()  ✓
6.  Retrieval functions (retrieval.py)  ✓
7.  Assessment Agent with structured JSON output (assessment_agent.py)  ✓
8.  Critic Agent with pass/fail loop (critic_agent.py)  ✓
9.  Presenter Agent: format final sections, no new reasoning (presenter_agent.py)  ✓
10. Dashboard display: tabbed report, citations, agent trace (app.py)  ✓
11. Follow-up input + Reassess workflow  ✓
12. Demo cases + trigger tests  ✓
```

Final one-line architecture:

```text
MarkItDown → Markdown → chunks → embeddings → Chroma → retrieval → Assessment Agent → Critic Agent (→ revise once if needed) → Citation resolver → Presenter Agent → Streamlit console
```
