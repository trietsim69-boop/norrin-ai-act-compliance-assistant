# Codebase status

Living progress tracker. **Last updated:** 2026-05-23

---

## Summary

| Area | Status |
|------|--------|
| MVP steps 1–12 | **Complete** |
| Streamlit regulatory console | **Complete** |
| Citation resolver + relevance | **Complete** |
| Trigger tests (mock, corpus loaded) | **5/5 pass** |
| Production / legal certification | **Out of scope** |

---

## Done

### Data & retrieval

- [x] MarkItDown preprocessing (`preprocessing.py`)  
- [x] Chunking with overlap (`chunking.py`)  
- [x] Chroma uploaded + corpus collections (`vector_store.py`)  
- [x] One-shot corpus loader (`scripts/load_corpus.py`) — ~1,874 chunks  
- [x] Corpus metadata enrichment (`corpus_metadata.py`)  
- [x] RAG retrieval — 8 standard queries + targeted pulls (`retrieval.py`)  

### Agents & pipeline

- [x] Assessment Agent — hybrid ReAct, structured JSON  
- [x] Critic Agent — checklist, pass/fail, revision instruction  
- [x] Presenter Agent — deterministic formatting (no LLM)  
- [x] Pipeline orchestrator — one revision max, `history[]`  
- [x] Citation resolver + relevance scoring  
- [x] LLM wrapper + mock mode  

### UI (`app.py`)

- [x] Cream/light regulatory console theme  
- [x] Top nav: Assessment Console, Regulatory Library, Audit Logs  
- [x] Intake: upload + manual description  
- [x] Sidebar: case metadata, New case, Reassess  
- [x] Results: risk hero, metrics, session actions  
- [x] Tabbed report: Overview, Assessment, Governance, Facts, Missing, Citations, Trace  
- [x] Right column: System Context + agent timeline  
- [x] Export Brief (JSON)  
- [x] Human-readable citation sources; debug chunk IDs hidden  

### Evaluation

- [x] Five demo case folders (14 sample files)  
- [x] `tests/expected_triggers.json`  
- [x] `scripts/run_trigger_tests.py`  
- [x] `src/evaluation.py`  

### Documentation

- [x] README, AGENTS, docs/ tree, demo_cases/README  

---

## In progress

- [ ] Citation “surrounding passage” UX (reduce confusing raw chunk expanders)  
- [ ] Real-LLM regression runs documented with pass/fail log  

---

## Not done / future

- [ ] PDF/Markdown report export  
- [ ] Bundled predictive-maintenance demo case + trigger entry  
- [ ] Automated malicious / out-of-scope input trigger test  
- [ ] Section-aware chunking for cleaner legal excerpts  
- [ ] Deployment packaging (Streamlit Cloud / Docker)  
- [ ] Persistent audit log storage across sessions  

---

## Known issues

| Issue | Impact | Workaround |
|-------|--------|------------|
| Full source text may start mid-section | Citations look “random” | Use excerpt + explanation; improve chunking later |
| `MOCK_LLM` shell override | Confusing mode switches | Set `$env:MOCK_LLM` explicitly before run |
| Live LLM latency | 2–5+ min per assessment | Use mock for demos |
| Critic may still pass with imperfect cites (live) | Quality variance | Show Trace + human review disclaimer |
| Sidebar + wide layout on small screens | Cramped UI | Widen browser; collapse sidebar |

---

## Next priorities

1. Polish citation expander (surrounding context only)  
2. Run `--real-llm` trigger tests and record results  
3. Optional PDF export for judges  
4. Add industrial PM demo case if time permits  

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
- Setup: [`setup_and_run.md`](setup_and_run.md)  
- Evaluation: [`evaluation_and_trigger_tests.md`](evaluation_and_trigger_tests.md)  
