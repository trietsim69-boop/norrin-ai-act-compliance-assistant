# Demo cases — sample inputs

Markdown document sets that simulate what a user uploads for **one AI use case**. Used for **manual Streamlit demos** and **automated trigger tests**.

Run tests: [`docs/evaluation_and_trigger_tests.md`](../docs/evaluation_and_trigger_tests.md)  
Live demo script: [`docs/demo_guide.md`](../docs/demo_guide.md)

---

## How to use in Streamlit

1. Upload **all files** from one folder below (or paste similar manual text)  
2. Optional: fill sidebar **Case metadata**  
3. **Run assessment**  
4. Compare risk tier, citations, and Trace to expected behaviour below  

With `MOCK_LLM=true`, the Assessment Agent picks fixtures from **keywords** in the uploaded text.

---

## Case index

| Folder | AI Act path | Mock risk expectation |
|--------|-------------|------------------------|
| [`hr_screening/`](hr_screening/) | Annex III employment | High-risk candidate |
| [`customer_chatbot/`](customer_chatbot/) | Art. 50 transparency | Limited risk |
| [`workplace_emotion_detection/`](workplace_emotion_detection/) | Art. 5(1)(f) workplace emotion | Prohibited / unacceptable |
| [`spam_filter/`](spam_filter/) | Narrow classification | Minimal risk |
| [`llm_report_generator/`](llm_report_generator/) | Chapter V GPAI deployer | GPAI obligations apply |
| [`predictive_maintenance/`](predictive_maintenance/) | Industrial LSTM PM | Minimal risk |

---

## `predictive_maintenance/` — Industrial predictive maintenance

**Expected:** **Minimal risk** (not HR/recruitment; custom LSTM, not GPAI)

### Files

| File | Role |
|------|------|
| `technical_overview.md` | MachineGuard PM — sensors, LSTM, technicians review alerts |

### Key signals

Predictive maintenance, industrial, machinery, LSTM, sensors — **not** recruitment, **not** foundation model

### Expected missing / follow-up themes

- Safety component integration (Article 6)  
- Deployment context  

### Why useful

Tests **citation correctness** — employment Annex III must **not** appear as strong primary evidence; weak/unsupported citations go to debug expander. Automated in trigger tests with `citation_checks`.

## `hr_screening/` — HR candidate screening

**Expected:** **High-risk candidate** (Annex III area 4 — employment / recruitment)

### Files

| File | Role |
|------|------|
| `product_description_talentrank.md` | Product overview — CV scoring, ranking |
| `hr_process_note.md` | Internal HR workflow |
| `policy_human_review.md` | Human review policy (partial oversight) |

### Key signals

Recruitment, applicants, ranking, shortlist, human recruiter review

### Expected missing / follow-up themes

- Human oversight depth  
- Decision impact on candidates  
- Provider vs deployer role  

### Why useful

Tests **high-risk employment** path, legal citations to Annex III, and critic behaviour on confidence vs oversight gaps.

---

## `customer_chatbot/` — Customer support chatbot

**Expected:** **Limited risk** (transparency / Art. 50 style obligations)

### Files

| File | Role |
|------|------|
| `chatbot_product_description.md` | Customer-facing chatbot description |
| `technical_overview.md` | LLM backend, integration |
| `transparency_notice_draft.md` | Draft disclosure notice |

### Key signals

Chatbot, customer interaction, LLM, transparency, disclosure

### Expected missing / follow-up themes

- Transparency implementation  
- GPAI use if applicable  

### Why useful

Tests **limited-risk / transparency** path distinct from high-risk employment.

---

## `workplace_emotion_detection/` — Workplace emotion analytics

**Expected:** **Prohibited or unacceptable** (workplace emotion recognition — Art. 5)

### Files

| File | Role |
|------|------|
| `vendor_pitch_moodsense.md` | Vendor sales pitch |
| `technical_overview_emotion.md` | Technical capabilities |
| `workplace_deployment_note.md` | Deployment in office setting |

### Key signals

Emotion, facial expression, employees, workplace, inference on workers

### Expected missing / follow-up themes

- What exactly is inferred  
- Deployment context and consent  

### Why useful

Tests **prohibited practice** detection and strong governance warnings.

---

## `spam_filter/` — Email spam filter

**Expected:** **Minimal risk**

### Files

| File | Role |
|------|------|
| `product_description_mailguard.md` | Product summary |
| `technical_overview_spam.md` | Narrow classification task |

### Key signals

Spam, filter, email, procedural classification, not high-stakes decision

### Expected missing / follow-up themes

- Usually fewer gaps (mock fixture uses high confidence on narrow task)

### Why useful

Tests **minimal risk** baseline — system should not over-classify as high-risk.

---

## `llm_report_generator/` — LLM internal report tool

**Expected:** **GPAI obligations apply** (deployer using third-party model)

### Files

| File | Role |
|------|------|
| `product_brief_insightwriter.md` | Internal report generator product |
| `internal_policy_gpai.md` | GPAI / third-party LLM policy notes |

### Key signals

GPT, LLM, third-party API, internal reports, deployer, foundation model

### Expected missing / follow-up themes

- Provider compliance documentation  
- Human review of generated reports  
- Downstream high-risk use of outputs  

### Why useful

Tests **GPAI deployer** path — common hackathon “API access” scenario. Deployment context often **unclear** → expect **low confidence** in live mode.

---

## Trigger test expectations

See [`tests/expected_triggers.json`](../tests/expected_triggers.json) for machine-readable checks (`expected_risk_direction`, `must_ask_about`, `min_legal_citations`, …).

```powershell
python -m scripts.run_trigger_tests --case hr_screening --verbose
```

---

## Related docs

- [`../README.md`](../README.md)  
- [`../docs/demo_guide.md`](../docs/demo_guide.md)  
