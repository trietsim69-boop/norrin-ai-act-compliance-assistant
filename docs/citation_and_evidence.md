# Citations and evidence

How the Norrin assistant separates **facts**, **regulatory references**, and **agent conclusions** — and why raw chunk IDs are not shown to users.

---

## Design principle

Users and judges should see **readable legal sources** (e.g. “EU AI Act — Annex III”), not internal retrieval IDs like `corpus_EU_AI_Act_chunk237`.

Internal IDs remain available under **Debug — chunk ID** for developers.

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

The Presenter and `citation_relevance.py` keep **uploaded facts** and **corpus law** visually and structurally distinct.

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
| `excerpt` | Best sentence from chunk (not blind prefix cut) |
| `full_text` | Retrieved chunk text (may start mid-section — see limitations) |
| `found` | Whether resolver located the chunk |
| `resolver` | `chroma` / `evidence_cache` / `chunk_id_heuristic` |

---

## Citation card (UI / Presenter)

Built by Presenter + `enrich_citation_row()`:

| Field | Shown to user |
|-------|---------------|
| **Claim** | What this evidence supports |
| **Category** | Supported fact / Regulatory reference / Governance note |
| **Source** | Readable label (not raw chunk ID) |
| **Type** | Regulation, Official guidance, Uploaded document, … |
| **Legal layer / Topic** | When available from corpus metadata |
| **Excerpt** | Quoted passage in italics |
| **Why this supports the claim** | `relevance_explanation` from scoring |
| **Full source text** | Expander — retrieved chunk (surrounding context) |
| **Debug — chunk ID** | Developer expander only |

### Primary vs additional

`citation_relevance.py` scores claim↔excerpt fit:

- **Primary** (`display_tier=primary`) — strong match, shown by default  
- **Additional** — weaker matches in collapsible section  

### System inference block

Agent conclusions (risk tier reasoning, AI system definition narrative) appear **above** citation cards with an explicit note that they are **inferences**, not verbatim law.

Reasoning text in UI strips raw `(corpus_…_chunkN)` parentheticals via display helpers in `app.py`.

---

## Source separation in the report

```text
Uploaded evidence  →  fact cards (purpose, sector, …)
Corpus evidence    →  legal basis + regulatory reference cards
Agent reasoning    →  system inference section (qualified language)
Missing facts      →  missing info tab (no fake citations)
```

---

## Known limitations

1. **Chunk boundaries** — Corpus is split ~800 chars with overlap. “Full source text” may start mid-paragraph or mid-Article list item `(b)(c)(d)` without `(a)`.  
2. **Retrieval misses** — Wrong or weak chunks produce weak citations; Critic may fail or warn.  
3. **Heuristic resolver** — Fallback parsing when Chroma miss is less precise than direct lookup.  
4. **Not exhaustive law** — Only indexed corpus (~1,874 chunks), not every EUR-Lex cross-reference.  
5. **No guarantee of legal accuracy** — Citations show **what was retrieved**, not certified legal interpretation.  

**Improvement path:** section-aware chunking, adjacent-chunk expansion, curated legal anchors, stronger relevance ranking.

---

## Related docs

- Multi-agent grounding: [`multi_agent_pipeline.md`](multi_agent_pipeline.md)  
- Architecture: [`architecture.md`](architecture.md)  
- Agent roles: [`../AGENTS.md`](../AGENTS.md)  
