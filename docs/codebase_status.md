# Codebase status

Living progress tracker. **Last updated:** 2026-05-24

---

## Summary

| Area | Status |
|------|--------|
| MVP steps 1–12 | **Complete** |
| Streamlit regulatory console | **Complete** |
| Citation validation + relevance + resolver | **Complete** |
| Scoped corpus retrieval | **Complete** |
| Trigger tests (mock, corpus loaded) | **6/6 pass** |
| Citation unit tests | **13/13 pass** |
| Production / legal certification | **Out of scope** |

---

## Done

### Data & retrieval

- [x] MarkItDown preprocessing (`preprocessing.py`)  
- [x] Chunking with overlap (`chunking.py`)  
- [x] Chroma uploaded + corpus collections (`vector_store.py`)  
- [x] One-shot corpus loader (`scripts/load_corpus.py`) — ~1,874 chunks  
- [x] Corpus metadata enrichment (`corpus_metadata.py`)  
- [x] RAG retrieval — standard queries + **scoped corpus queries** + targeted pulls (`retrieval.py`)  

### Agents & pipeline

- [x] Assessment Agent — hybrid ReAct, structured JSON, citation discipline prompts  
- [x] **Assessment-time citation validation** (`citation_validation.py`) — repair before Critic  
- [x] Critic Agent — checklist incl. citation relevance; **cited chunk text** in prompt  
- [x] Presenter Agent — support tiers, primary/weak/unsupported buckets  
- [x] Pipeline orchestrator — one revision max, `history[]`  
- [x] Citation resolver + relevance scoring (0–1 support_score, legal topic routing)  
- [x] LLM wrapper + mock mode (six demo fixtures incl. predictive maintenance)  

### UI (`app.py`)

- [x] Cream/light regulatory console theme  
- [x] Top nav: Assessment Console, Regulatory Library, Audit Logs  
- [x] Intake: upload + manual description  
- [x] Sidebar: case metadata, New case, Reassess  
- [x] Results: risk hero, metrics, session actions  
- [x] Tabbed report: Overview, Assessment, Governance, Facts, Missing, Citations, Trace  
- [x] Right column: System Context + agent timeline  
- [x] Export Brief (JSON)  
- [x] Citation cards: **Support** label, weak/unsupported warnings, debug chunk IDs  
- [x] Unsupported citations hidden from Legal basis; shown in debug expander  

### Evaluation

- [x] Six demo case folders  
- [x] `tests/expected_triggers.json` (incl. `predictive_maintenance`, `citation_checks`)  
- [x] `tests/test_citation_relevance.py`, `tests/test_citation_validation.py`  
- [x] `scripts/run_trigger_tests.py`  
- [x] `src/evaluation.py`  

### Documentation

- [x] README, AGENTS, docs/ tree, demo_cases/README  

---

## In progress

- [ ] Real-LLM regression runs documented with pass/fail log  

---

## Not done / future

- [ ] PDF/Markdown report export  
- [ ] Automated malicious / out-of-scope input trigger test  
- [ ] Section-aware chunking for cleaner legal excerpts  
- [ ] Structured per-claim legal citations in assessment JSON schema  
- [ ] Deployment packaging (Streamlit Cloud / Docker)  
- [ ] Persistent audit log storage across sessions  

---

## Known issues

| Issue | Impact | Workaround |
|-------|--------|------------|
| Full source text may start mid-section | Citations look “random” in expander | Use excerpt + support label; rely on claim-selected excerpt |
| `MOCK_LLM` shell override | Confusing mode switches | Set `$env:MOCK_LLM` explicitly before run |
| Live LLM latency | 2–5+ min per assessment | Use mock for demos |
| Flat `legal_citations` array | Hard to bind cite to sub-claim | Presenter + relevance infer claim context |
| Sidebar + wide layout on small screens | Cramped UI | Widen browser; collapse sidebar |

---

## Next priorities

1. Run `--real-llm` trigger tests and record results  
2. Optional PDF export for judges  
3. Per-claim citation structure in assessment JSON  

---

## Update protocol

On major changes, update this file in the same commit:

1. Bump **Last updated** date  
2. Move items between Done / In progress / Not done  
3. Add known issues when discovered  
4. Keep aligned with [`mvp_plan.md`](mvp_plan.md)  

---

## Related docs

- Architecture: [`architecture.md`](architecture.md)  
- Citations: [`citation_and_evidence.md`](citation_and_evidence.md)  
- Setup: [`setup_and_run.md`](setup_and_run.md)  
- Evaluation: [`evaluation_and_trigger_tests.md`](evaluation_and_trigger_tests.md)  
