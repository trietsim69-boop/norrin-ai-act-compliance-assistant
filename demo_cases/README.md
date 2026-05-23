# Demo cases

Sample document sets for the five MVP evaluation paths. Each folder contains Markdown files that mirror what a user might upload for a single AI use case.

| Folder | AI Act path tested | Key signals in documents |
|--------|-------------------|--------------------------|
| `hr_screening/` | High-risk (Annex III employment) | recruitment, candidate ranking, human review |
| `customer_chatbot/` | Limited risk / transparency (Art. 50) | chatbot, LLM, transparency notice |
| `workplace_emotion_detection/` | Prohibited practice (Art. 5(1)(f)) | emotion recognition, workplace, employees |
| `spam_filter/` | Minimal risk | spam filter, narrow classification task |
| `llm_report_generator/` | GPAI deployer obligations | third-party GPT/LLM, internal report generation |

## Running trigger tests

From the project root (dependencies installed, corpus loaded):

```powershell
python -m scripts.run_trigger_tests
python -m scripts.run_trigger_tests --case hr_screening --verbose
python -m scripts.run_trigger_tests --real-llm
```

With `MOCK_LLM=true` (default in `.env`), the Assessment Agent selects fixtures based on keywords in the indexed demo documents. With `MOCK_LLM=false`, the same documents run through the live LLM pipeline.

Expected outcomes: [`tests/expected_triggers.json`](../tests/expected_triggers.json)

## Using in the Streamlit UI

1. Start the app: `streamlit run app.py --server.port 8521`
2. Upload all files from one demo folder **or** paste a manual description with similar keywords
3. Click **Run assessment**
4. Optional: fill in sidebar **Case metadata** (use-case name, sector, org role, deployment context, region, GPAI notes)

After a run, use **New case** (clears session) or **Reassess** (same files/metadata, re-runs pipeline) from the results bar, sidebar, or right-column quick actions.

Use **Regulatory Library** in the top nav to confirm the corpus is loaded (1,874 chunks). Use **Audit Logs** to inspect pipeline stages for the current session.
