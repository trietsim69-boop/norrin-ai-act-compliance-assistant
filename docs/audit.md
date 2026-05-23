# Audit — norrin-ai-act-compliance-assistant

**Date:** 2026-05-23 · **Branch:** `refactor` · **Audit scope:** check the code against the legal scope defined by the two Commission Guidelines (`corpus/*.PDF`), plus a correctness & hygiene review.

---

## 0. Scope context (what the two PDFs define)

| PDF | Legal scope the assistant must cover |
|---|---|
| **Definition guideline** (definition of an AI system, Art 3) | The 7 elements of the definition **+ the OUT-OF-SCOPE categories**: basic data processing, classical heuristics, simple prediction systems, mathematical optimization (§5.2, paras 40–51) |
| **Prohibited practices guideline** (Art 5) | **8 prohibited practices** Art 5(1)(a)–(h): manipulation/deception, exploitation of vulnerabilities, social scoring, crime prediction (predictive policing), untargeted scraping of facial images, emotion recognition (workplace/education), biometric categorisation, real-time remote biometric identification |

**Overall:** clean architecture, faithful to `AGENTS.md` (three role-separated agents, structured JSON, bounded revision loop, mock mode, retrieval as the boundary). Steps 1–11 done; step 12 (tests + demo cases) not done. However there are **2 major scope gaps**, **1 UI crash bug**, and a few technical items to clean up.

---

## 🔴 A. SCOPE gaps (vs the two PDFs — most important)

### A1. Only 1 of 8 prohibited practices is actually reachable by retrieval
`STANDARD_QUERIES` (`src/retrieval.py:8-17`) only probes **emotion recognition + biometric/facial**. There is no query for the other 6 prohibited practices (social scoring, manipulation/deception, exploitation, crime prediction, untargeted scraping, real-time RBI).

Because **retrieval is the boundary** (agents only see returned chunks), the system structurally **cannot** surface 7 of the 8 prohibited practices — unless the LLM happens to request more via `needs_more_evidence`. The corpus holds 767 prohibited-guidance chunks that are never pulled up.

- **Impact:** a social-scoring or predictive-policing use case will likely be misclassified (not flagged as prohibited).
- The `risk_tier` enum has a single `prohibited` bucket with no sub-typing per point (a)–(h).
- **Suggested fix:** add queries covering all 8 practices; consider sub-typing the `prohibited` tier.

### A2. The "out-of-scope of the AI system definition" reasoning is entirely missing
`ASSESSMENT_SYSTEM_PROMPT` (`src/agents/assessment_agent.py:38-90`) only says *"Whether the system meets the AI Act definition (Article 3)"* — it does **not** mention the 7 elements, nor the exclusion categories that the entire second half of the Definition guideline is about.

The consequence shows in mock: `_MOCK_SPAM` asserts `ai_system: "yes"` (`assessment_agent.py:419`), yet a rule-/statistics-based spam filter is exactly the kind of system the guideline flags as **potentially outside the definition**. The agent never tests the "inference beyond basic data processing" criterion.

- **Impact:** a bias toward over-including systems as "AI systems", contrary to the Definition guideline's purpose.
- **Suggested fix:** put the 7 elements + the out-of-scope criteria into the prompt; allow `ai_system: "no"` with an exclusion rationale.

### A3. (Low) Annex III probes only 1 of 8 domains
Queries only ask about employment/recruitment; Annex III has 8 high-risk domains. Adequate for the 5 demos but narrow vs the full scope — acceptable at MVP level.

---

## 🔴 B. Code bugs

### B1. `app.py:362` — mutating widget state after the widget is rendered (will crash)
```python
new_answer = st.text_area(..., key="follow_up_input", ...)   # line 355
if st.button("Apply and re-run"):
    ...
    st.session_state["follow_up_input"] = ""                 # line 362
```
Re-assigning `st.session_state["follow_up_input"]` **after** the widget with the same key was instantiated in the same run makes Streamlit raise `StreamlitAPIException`. So the follow-up re-run feature (step 11, marked "done") **will break when clicked**. *(Should be confirmed with `streamlit run`, but this is a classic Streamlit error.)*
- **Fix:** clear the input via an `on_click` callback or `st.session_state.pop(...)` before the widget is created — never assign after.

### B2. `pipeline.py` runs retrieval twice
`pipeline.py:45-49` retrieves baseline context for the critic; `assessment_agent` (`assessment_agent.py:121`) **re-retrieves the exact same baseline** internally (it ignores the pipeline's chunks). Each run does the embed/query work twice (4× when a revision happens), and the two retrievals can drift apart.
- **Fix:** retrieve once, then pass the chunks into the agent.

### B3. Mock citations are fabricated IDs (mock mode only = the default demo mode)
Fixtures cite `"corpus:article_5_1_f"`, `"uploaded:chunk0"`… but the real chunk_ids produced by `chunking.py` are `{session}_{stem}_chunkN` and `corpus_{stem}_chunkN`. Under `MOCK_LLM=true` (the default), the critic uses heuristics that never check ID existence → the "evidence-grounded / citations" story is cosmetic; citations don't resolve to real chunks. Fine for offline dev, but the demo's headline feature (evidence separation) **is never actually exercised** in mock mode.
- **Suggested fix:** make mocks cite real IDs, or state clearly that mock citations are illustrative.

### B4. Presenter's evidence separation relies on a fragile string heuristic
`presenter_agent.py:304-312` (`_bucket`): treats a citation as corpus if it starts with `"corpus"` or contains `"annex"/"article"`. An uploaded file named e.g. `article_5_policy.pdf` → chunk_id contains "article" → misfiled as corpus.
- **Fix:** tag each citation by its source set (uploaded/corpus) at retrieval time, rather than guessing from the ID string.

---

## 🟡 C. Hygiene / process

- **C1. Step 12 not done:** no `tests/expected_triggers.json`, no `demo_cases/`. This trigger-based eval is exactly what would verify A1/A2. (codebase_status honestly notes this.)
- **C2.** `README.md` is a single line (though `AGENTS.md` & docs are excellent).
- **C3. Security is sound:** `.env` not tracked, `.gitignore` solid, keys read from env, nothing hardcoded. ✅
- **C4. Minor doc drift:** `AGENTS.md` still says `app.py`/presenter are "not built yet" although they are built; codebase_status says Python 3.13+ (the audit environment is 3.12 — not a repo issue).

---

## Priority order

| # | Action | Why |
|---|---|---|
| 1 | **B1** fix the `follow_up_input` bug | crashes a feature marked "done" |
| 2 | **A1** add queries for all 8 prohibited practices + (optional) sub-type `risk_tier` | core scope of the prohibited PDF |
| 3 | **A2** put the 7 elements + out-of-scope criteria into the assessment prompt | core scope of the definition PDF |
| 4 | **C1** write `demo_cases/` + trigger tests | the only way to prove A1/A2 are fixed |
| 5 | B2 / B3 / B4 technical cleanup | quality & trustworthiness |

---

## Appendix — methodology

- The audit machine had no `pip`/`apt`/poppler, so the two PDFs were extracted with a pure-Python script (`zlib` decompression of content streams + text-operator parsing) to read the guideline text.
- Read the whole of `src/`, `app.py`, `scripts/`, `docs/`, config, and `.gitignore`.
- All `file:line` references reflect the `refactor` branch at commit `b9b3615`.
