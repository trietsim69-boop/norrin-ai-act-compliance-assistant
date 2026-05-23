# Demo guide (judges & presenters)

Live demo script for the Norrin AI Act Compliance Assistant. Allow **5–8 minutes** plus Q&A.

**Before you start:** corpus loaded, app running, `MOCK_LLM=true` for reliable offline demo (switch to live only if API is verified).

```powershell
python -m scripts.load_corpus
$env:MOCK_LLM = "true"
streamlit run app.py --server.port 8521
```

---

## Demo flow overview

1. Show **Regulatory Library** (corpus loaded)  
2. Run **Demo 1 — HR screening** (high-risk path)  
3. Show report, **Trace**, **Citations**  
4. Optional **Demo 2 — GPAI / LLM tool** (obligations path)  
5. Mention **Critic + revision** if visible  
6. Close with **limitations** (not legal advice)  

---

## Demo 1 — HR candidate screening (recommended)

**Folder:** `demo_cases/hr_screening/`

**Files to upload (all three):**

- `product_description_talentrank.md`  
- `hr_process_note.md`  
- `policy_human_review.md`  

### What to click

1. **Assessment Console** (top nav)  
2. Upload all three files in **Upload documents**  
3. Sidebar → **Case metadata:**  
   - Use-case name: `TalentRank HR screening`  
   - Sector: `Employment / HR`  
   - Organisation role: `deployer`  
4. **Run assessment** — watch progress bar  
5. After results appear, point to **risk hero** (expect high-risk / Annex III employment signals in mock mode)  

### What to explain

- “We ingest documents, chunk them, and retrieve both **your uploads** and the **built-in EU AI Act corpus**.”  
- “The **Assessment Agent** produces structured JSON — facts, risk tier, citations.”  
- “The **Critic Agent** checks grounding; it can trigger **one revision**.”  
- “The **Presenter** formats the report — it does **not** add new legal reasoning.”  

### What to show

| UI area | Talking point |
|---------|---------------|
| **Metrics row** | Risk tier, legal triggers, confidence, critic status |
| **Overview tab** | Summary + warnings + top follow-ups |
| **Assessment tab** | AI system definition + risk reasoning + legal basis cards |
| **Facts tab** | Evidence from uploads with confidence |
| **Missing info tab** | Gaps — human oversight, deployer role |
| **Citations tab** | Regulatory references vs system inference |
| **Trace tab** | assessment_v1 → critic_v1 → [v2] → presenter |
| **Right column** | System Context + agent timeline |
| **Audit Logs** (nav) | Same history, session id |

### Expected outputs (mock mode)

- Risk direction: **high-risk candidate** (Annex III employment)  
- Legal citations present  
- Follow-up questions about oversight / decision impact  
- Critic stage in history  

---

## Demo 2 — GPAI / LLM report tool (second path)

**Folder:** `demo_cases/llm_report_generator/`

**Files:** `product_brief_insightwriter.md`, `internal_policy_gpai.md`

**Note:** A bundled **predictive maintenance** demo folder is available at `demo_cases/predictive_maintenance/`. Use it to show citation validation — wrong-domain law is downgraded, not shown as strong proof.

### Expected outputs (mock mode)

- Risk direction: **GPAI obligations apply**  
- Follow-ups about provider compliance, human review  
- Confidence may be **low** if deployment context is thin  

---

## Demo 3 — Quick “prohibited practice” (optional, 2 min)

**Folder:** `demo_cases/workplace_emotion_detection/`

Upload all three `.md` files → expect **prohibited / workplace emotion** signals in mock mode.

---

## How to show multi-agent trace

1. Open **Trace** tab **or** top nav → **Audit Logs**  
2. Expand **Raw output — critic_v1** (issues, pass/fail)  
3. If `revision_triggered`, show **assessment_v2** and **critic_v2**  
4. Right-column timeline: **DONE / REVISE / PASS** badges  

Say: “Every stage is stored in `history[]` — not a single black-box completion.”

---

## How to show citations

1. **Citations** tab  
2. Point to **System inference** block (agent conclusion, not a quote)  
3. Open a primary card — note **Support:** Strong / Moderate and readable **Source** + excerpt  
4. If weak: open **Additional evidence** expander — amber warning explains limited support  
5. **Unsupported / debug evidence** expander — citations stripped or rejected by validation/scoring  
6. Chunk IDs under **Debug** only ([`citation_and_evidence.md`](citation_and_evidence.md))  

**Predictive maintenance demo:** upload [`demo_cases/predictive_maintenance/technical_overview.md`](../demo_cases/predictive_maintenance/technical_overview.md) — expect minimal risk; HR Annex III must not appear as strong primary citation.

---

## How to show follow-up questions

1. **Missing info** tab — gap cards + suggested questions  
2. Optional: type clarification → **Update assessment** (re-runs pipeline)  
3. Or **Reassess** from session actions (same inputs, fresh run)  

---

## Backup plan if API fails

1. Set `$env:MOCK_LLM = "true"` and restart Streamlit  
2. Use **hr_screening** demo files — fixtures activate on keywords (`recruit`, `hiring`, …)  
3. Show **Regulatory Library** — proves corpus is local, not pasted into prompt  
4. Show **Trace** + **Citations** — multi-agent and grounding story still holds  
5. Honest line: “Live LLM path uses the same pipeline; mock mode proves architecture for judging.”  

---

## After demo — limitations (30 seconds)

- Preliminary only, **not legal advice**  
- Citations depend on chunk retrieval quality  
- EU AI Act guidance still evolving  
- Human expert must validate before decisions  

---

## Related docs

- Demo case details: [`../demo_cases/README.md`](../demo_cases/README.md)  
- Multi-agent: [`multi_agent_pipeline.md`](multi_agent_pipeline.md)  
- Setup: [`setup_and_run.md`](setup_and_run.md)  
