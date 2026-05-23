# Evaluation and trigger tests

Automated checks that demo cases trigger the **expected EU AI Act reasoning paths**.

Implementation: `src/evaluation.py`, `scripts/run_trigger_tests.py`, expectations in `tests/expected_triggers.json`.

---

## Running tests

```powershell
# All cases, mock LLM (default)
python -m scripts.run_trigger_tests

# One case, verbose
python -m scripts.run_trigger_tests --case hr_screening --verbose

# Live LLM (requires API key, slower, stricter)
python -m scripts.run_trigger_tests --real-llm
```

**Prerequisites:** dependencies installed, **`python -m scripts.load_corpus`** completed.

**Mock target:** **5/5 pass** when corpus is loaded.

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

Example output snippet:

```text
hr_screening: PASS (6/6 checks)
  ✓ risk_direction
  ✓ domain_trigger
  ✓ follow_up: human oversight
  ...
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
| Predictive maintenance → minimal/unclear | **Not a bundled case** — use manual description or custom upload; no automated trigger entry yet |
| Malicious / out-of-scope input | **Not automated** — handle cautiously in UI; no dedicated trigger test |
| Weak evidence → critic revision | Observed ad hoc when live LLM + thin uploads; mock critic uses heuristics |

---

## Mock vs real LLM

| Mode | Assessment source | Use case |
|------|-------------------|----------|
| Mock (`MOCK_LLM=true`) | Keyword → fixture in `assessment_agent.py` | CI-style regression, hackathon demo reliability |
| Real (`--real-llm`) | Live model + ReAct | Integration validation; may fail if prompts/API drift |

---

## Adding a new trigger case

1. Create `demo_cases/{slug}/` with representative `.md` files  
2. Add entry to `tests/expected_triggers.json`  
3. Add mock fixture keywords in `assessment_agent._pick_mock_fixture()` if using mock mode  
4. Run `python -m scripts.run_trigger_tests --case {slug} --verbose`  

---

## Related docs

- Demo case file lists: [`../demo_cases/README.md`](../demo_cases/README.md)  
- Demo presentation: [`demo_guide.md`](demo_guide.md)  
- Multi-agent behaviour: [`multi_agent_pipeline.md`](multi_agent_pipeline.md)  
