# Citations and evidence

How the Norrin assistant separates **facts**, **regulatory references**, and **agent conclusions** — and why raw chunk IDs are not shown to users.

**Core principle:** The goal is not “more citations.” The goal is **“no fake strong citations.”** If the source text does not directly support the claim, it must not appear as primary evidence.

---

## Design principle

Users and judges should see **readable legal sources** (e.g. “EU AI Act — Annex III”), not internal retrieval IDs like `corpus_EU_AI_Act_chunk237`.

Internal IDs remain available under **Debug — chunk ID** for developers.

---

## Pipeline (citation path)

```text
Retrieval (scoped corpus queries)
  → Assessment Agent (LLM assigns chunk_id arrays)
  → validate_and_repair_assessment()   ← strips bad citations at source
  → Critic Agent (pass/fail + cited chunk text)
  → resolve_citations()                ← chunk_id → evidence cards
  → enrich_citation_row()              ← support_score, excerpt, tiers
  → Presenter + Streamlit UI
```

| Stage | Module | Role |
|-------|--------|------|
| **Validation** | `src/citation_validation.py` | Remove invalid IDs before Critic; enforce source-type + topic rules |
| **Resolution** | `src/citation_resolver.py` | Map IDs to text + metadata (Chroma → cache → heuristic) |
| **Relevance** | `src/citation_relevance.py` | Score claim↔excerpt fit; assign support tier |
| **Presentation** | `src/agents/presenter_agent.py` | Bucket primary / additional / unsupported |

---

## Evidence types

| Type | `evidence_type` | Typical source |
|------|---------------|----------------|
| **Uploaded document** | `uploaded_document` | User PDF/DOCX converted to chunks |
| **Regulation** | `regulation` | EU AI Act HTML corpus |
| **Official guidance** | `official_guidance` | Commission guideline PDFs |
| **User input** | `user_input` | Manual use-case description chunk |
| **System inference** | (presented separately) | Assessment Agent reasoning — *not* a direct quote |
| **Assumption / unclear** | flagged in facts | Low confidence, missing evidence array |

**Source-type rules (enforced programmatically):**

| Claim | Must cite |
|-------|-----------|
| Uploaded-system facts (`extracted_facts.*.evidence`) | `uploaded_document` or `user_input` only |
| Legal rules (`preliminary_assessment.legal_citations`) | `regulation` or `official_guidance` only |
| Governance observations | Either, but must match the observation area |

Corpus chunks must **not** support factual claims about the user's system. Uploaded docs must **not** be sole support for legal rule claims.

---

## Assessment-time validation (`src/citation_validation.py`)

Runs **immediately after** each Assessment Agent LLM response (before Critic).

### Checks

1. **Evidence pack** — cited `chunk_id` must appear in chunks shown to the LLM (or valid mock alias)  
2. **Source-type separation** — corpus ≠ uploaded facts; uploads ≠ legal-only claims  
3. **Legal topic routing** — e.g. employment Annex III rejected for predictive-maintenance context  
4. **Support threshold (live mode)** — legal citations must score **strong** or **moderate**; facts may keep **weak**  

### Repairs

- Invalid citations **removed** from JSON arrays (not silently kept)  
- Confidence lowered when evidence stripped  
- `missing_information` entry added when repairs occur  
- Audit trail: `assessment._meta.citation_repairs[]`

---

## Citation resolver (`src/citation_resolver.py`)

**Not an agent** — called after Assessment + Critic finalize.

### Input

List of `chunk_id` strings collected from:

- `preliminary_assessment.legal_citations`  
- `extracted_facts[].evidence`  
- `governance_observations[].citations`  

### Resolution layers (in order)

1. **Chroma lookup** — fetch text + metadata from uploaded or corpus collection  
2. **Evidence cache** — match against chunks already retrieved this session  
3. **Chunk-ID heuristic** — parse `corpus_*` / `sess_*` filename patterns when lookup misses  

### Key output fields

| Field | Purpose |
|-------|---------|
| `source` / `source_label` | Human-readable title (via `format_source_label()`) |
| `evidence_type` | Regulation, guidance, upload, etc. |
| `section` | Article / Annex when parseable |
| `law_layer_label` | e.g. Definitions, Core rules, Prohibited practices |
| `topic_label` | e.g. High-risk classification, AI system definition |
| `excerpt` | Best 1–3 sentences for the **claim** (selected in `citation_relevance.py`) |
| `full_text` | Retrieved chunk text (expander only — may start mid-section) |
| `found` | Whether resolver located the chunk |
| `resolver` | `chroma` / `evidence_cache` / `chunk_id_heuristic` |

---

## Relevance scoring (`src/citation_relevance.py`)

Purely programmatic — does **not** call an LLM.

### Support tiers

| Label | Score | UI bucket |
|-------|-------|-----------|
| **strong** | ≥ 0.70 | Primary citation cards |
| **moderate** | 0.50 – 0.69 | Primary (may show mild caveat) |
| **weak** | 0.30 – 0.49 | Additional evidence expander |
| **unsupported** | < 0.30 | Unsupported / debug expander only |

### Scoring signals

- Keyword + entity overlap between claim and excerpt  
- Source-type match (hard gate)  
- Legal topic match vs use-case context (e.g. industrial PM vs HR Annex III)  
- Claim-aware excerpt selection from `full_text`  

### Fields on each citation card

| Field | Shown to user |
|-------|---------------|
| **Support** | `strong` / `moderate` / `weak` / `unsupported` |
| **Claim** | What this evidence supports |
| **Category** | Supported fact / Regulatory reference / Governance note |
| **Source** | Readable label (not raw chunk ID) |
| **Excerpt** | Quoted passage in italics |
| **Why this supports the claim** | `relevance_explanation` |
| **Warning** | Shown when weak/unsupported: *“This source is related but does not directly prove the claim.”* |
| **Full source text** | Expander |
| **Debug — chunk ID** | Developer expander only |

### Primary vs additional vs unsupported

- **`citation_cards`** — strong + moderate only  
- **`additional_evidence`** — weak  
- **`unsupported_or_debug_evidence`** — unsupported (hidden from Legal basis tab)  

### System inference block

Agent conclusions (risk tier reasoning, AI system definition narrative) appear **above** citation cards with an explicit note that they are **inferences**, not verbatim law.

Reasoning text in UI strips raw `(corpus_…_chunkN)` parentheticals via display helpers in `app.py`.

---

## Source separation in the report

```text
Uploaded evidence  →  fact cards (purpose, sector, …)
Corpus evidence    →  legal basis + regulatory reference cards (supported only)
Agent reasoning    →  system inference section (qualified language)
Missing facts      →  missing info tab (no fake citations)
Weak citations     →  additional / unsupported expanders with warnings
```

---

## Retrieval scoping (`src/retrieval.py`)

To reduce wrong-domain corpus chunks in the LLM context:

- **Uploaded collection:** all standard queries (purpose, sector, affected persons, …)  
- **Corpus collection:** core queries always + **conditional** queries only when uploaded text signals match (employment, chatbot, emotion, GPAI)  
- **`infer_retrieval_targets`** — metadata-driven extra corpus pulls from uploaded signals  

Example: predictive maintenance uploads do **not** automatically trigger the employment/recruitment corpus query.

---

## Known limitations

1. **Chunk boundaries** — Corpus is split ~800 chars with overlap. “Full source text” may start mid-paragraph.  
2. **LLM variability** — Assessment may still *attempt* weak citations; validation + presenter filter them.  
3. **Heuristic resolver** — Fallback parsing when Chroma miss is less precise than direct lookup.  
4. **Not exhaustive law** — Only indexed corpus (~1,874 chunks).  
5. **No guarantee of legal accuracy** — Citations show **what was retrieved and validated**, not certified legal interpretation.  
6. **Flat `legal_citations` array** — Not yet tied to individual sub-claims in assessment JSON.  

---

## Related docs

- Multi-agent grounding: [`multi_agent_pipeline.md`](multi_agent_pipeline.md)  
- Architecture: [`architecture.md`](architecture.md)  
- Agent roles: [`../AGENTS.md`](../AGENTS.md)  
- Trigger tests: [`evaluation_and_trigger_tests.md`](evaluation_and_trigger_tests.md)  
