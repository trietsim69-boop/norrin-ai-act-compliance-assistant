# Evaluation and trigger tests

Automated checks that demo cases trigger the **expected EU AI Act reasoning paths**.

Implementation: `src/evaluation.py`, `scripts/run_trigger_tests.py`, expectations in `tests/expected_triggers.json`.

Unit tests: `tests/test_citation_relevance.py`, `tests/test_citation_validation.py`.

---

## Running tests

```powershell
# All cases, mock LLM (default)
python -m scripts.run_trigger_tests

# One case, verbose
python -m scripts.run_trigger_tests --case hr_screening --verbose

# Citation unit tests (no LLM, no Chroma)
python -m pytest tests/test_citation_relevance.py tests/test_citation_validation.py -v

# Live LLM (requires API key, slower, stricter)
python -m scripts.run_trigger_tests --real-llm
```

**Prerequisites:** dependencies installed, **`python -m scripts.load_corpus`** completed.

**Mock target:** **6/6 pass** when corpus is loaded.

---

## What each test does

For each demo case slug:

1. Load all `.md` / `.txt` files from `demo_cases/{slug}/`  
2. Chunk and index into Chroma (`demo_{slug}_…` session)  
3. Run **`run_assessment_pipeline()`**  
4. Score output against `expected_triggers.json`  

---

## Bundled demo cases and expectations

| Slug | Scenario | Expected risk direction | Domain trigger keywords |
|------|----------|-------------------------|-------------------------|
| `hr_screening` | HR candidate screening | `high_risk` | employment, recruit, Annex III |
| `customer_chatbot` | Support chatbot | `limited_risk` | chatbot, transparency, Art. 50 |
| `workplace_emotion_detection` | Workplace emotion analytics | `prohibited_or_unacceptable` | emotion, workplace, Art. 5 |
| `spam_filter` | Email spam filter | `minimal_risk` | spam, narrow filtering |
| `llm_report_generator` | Third-party LLM reports | `gpai_obligations` | GPAI, LLM, deployer |
| `predictive_maintenance` | Industrial LSTM PM | `minimal_risk` | maintenance, industrial, sensor |

Full expectations: [`tests/expected_triggers.json`](../tests/expected_triggers.json)

---

## Checks performed per case

| Check | Description |
|-------|-------------|
| **risk_direction** | Observed `risk_tier` matches expected bucket (aliases allowed) |
| **domain_trigger** | Assessment/corpus context contains trigger keywords |
| **must_ask_about** | Follow-up text mentions required phrases (e.g. “human oversight”) |
| **legal_citations** | Count of `legal_citations` ≥ minimum (default 1) |
| **critic_stage** | Pipeline `history` includes a critic stage |
| **required_sections** | Core assessment JSON sections present |
| **citation_support** | *(optional)* Primary cards have allowed support labels; forbidden topics absent |

### Citation support checks (`citation_checks` in JSON)

Example for `predictive_maintenance`:

```json
"citation_checks": {
  "forbid_strong_topics": ["employment_and_worker_management"],
  "require_support_label_primary": ["strong", "moderate"],
  "forbid_gpai_without_evidence": true
}
```

Example for `hr_screening`:

```json
"citation_checks": {
  "require_employment_topic_primary": true,
  "require_support_label_primary": ["strong", "moderate"]
}
```

---

## Mapping to challenge scenarios

| Scenario | Covered by |
|----------|------------|
| HR recruitment → high-risk candidate | `hr_screening` |
| Chatbot → limited / transparency | `customer_chatbot` |
| Prohibited workplace emotion | `workplace_emotion_detection` |
| Minimal / narrow task | `spam_filter` |
| GPAI / API access → obligations | `llm_report_generator` |
| Predictive maintenance → minimal/unclear | `predictive_maintenance` |
| Weak / wrong citations downgraded | Unit tests + `citation_checks` on PM case |
| Malicious / out-of-scope input | **Not automated** — handle cautiously in UI |

---

## Mock vs real LLM

| Mode | Assessment source | Citation validation | Use case |
|------|-------------------|---------------------|----------|
| Mock (`MOCK_LLM=true`) | Keyword → fixture | Remap mock IDs; topic rules only | CI regression, hackathon demo |
| Real (`--real-llm`) | Live model + ReAct | Full pack + support threshold | Integration validation |

---

## Adding a new trigger case

1. Create `demo_cases/{slug}/` with representative `.md` files  
2. Add entry to `tests/expected_triggers.json` (optional `citation_checks`)  
3. Add mock fixture keywords in `assessment_agent._pick_mock_fixture()` if using mock mode  
4. Run `python -m scripts.run_trigger_tests --case {slug} --verbose`  

---

## Related docs

- Demo case file lists: [`../demo_cases/README.md`](../demo_cases/README.md)  
- Citation design: [`citation_and_evidence.md`](citation_and_evidence.md)  
- Demo presentation: [`demo_guide.md`](demo_guide.md)  
- Multi-agent behaviour: [`multi_agent_pipeline.md`](multi_agent_pipeline.md)  
