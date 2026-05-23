# Multi-agent pipeline

**Primary document for hackathon judges** evaluating multi-agent design, autonomy, and grounding.

---

## Why this is multi-agent (not one big prompt)

| Concern | Single LLM call | This design |
|---------|-----------------|-------------|
| Legal reasoning vs formatting | Mixed in one output | **Assessment** reasons; **Presenter** formats only |
| Quality control | Hope the model self-checks | **Critic** explicitly pass/fails with issues list |
| Unsupported claims | Hard to audit | Critic flags; revision forces fix |
| Overconfidence | Common with one shot | Critic checks confidence vs evidence |
| Transparency | Black box | **`history[]`** shows every stage |

Each agent has a **distinct role**, **structured JSON contract**, and **autonomous decisions** within that role. The orchestrator (`src/pipeline.py`) wires them; agents do not call each other.

---

## Stage-by-stage

### 0 — Retrieval (not an agent)

`retrieve_combined_context()` gathers evidence **before** any agent runs.

- Uploaded chunks: session-scoped  
- Corpus chunks: global AI Act + guidance  
- No agent sees the vector DB directly  

### 1 — Assessment Agent (v1)

**Decides:** facts, risk tier, confidence, governance notes, legal citations, gaps, optional extra retrieval queries.

**Output:** Large structured JSON (see [`../AGENTS.md`](../AGENTS.md)).

**Stored as:** `history[stage=assessment_v1]`

### 2 — Critic Agent (v1)

**Decides:** pass or fail; issue categories; one revision instruction; missing questions for humans.

**Input:** Assessment JSON + same evidence chunks.

**Does not:** rewrite the assessment or retrieve new data.

**Stored as:** `history[stage=critic_v1]`

### 3 — Optional revision (bounded)

**Trigger:** `pass == false` and non-empty `revision_instruction`.

**Assessment Agent (v2)** receives previous assessment + instruction → revised JSON.

**Critic Agent (v2)** re-evaluates.

**Limit:** exactly **one** revision (`MAX_REVISIONS = 1` in pipeline). No infinite loops.

**Flag:** `_meta.revision_triggered = true`

### 4 — Citation resolution

Collect all `chunk_id` references from final assessment → `resolve_citations()` → lookup map for Presenter and UI.

Not an agent — deterministic + Chroma lookups.

### 5 — Presenter Agent

**Decides (formatting only):** section layout, warning severity, citation tiers, disclaimer.

**Does not:** call LLM or add new legal conclusions.

**Stored as:** `history[stage=presenter]`

---

## How agents communicate

Communication is **structured JSON passed by the orchestrator** — not natural-language chat between agents.

```text
pipeline.run_assessment_pipeline()
  ├─ assessment: dict     ──► critic_agent(assessment, chunks)
  ├─ critic: dict         ──► [revision] assessment_agent(..., revision_instruction=...)
  ├─ assessment (final)   ──► resolve_citations + presenter_agent
  └─ presented: dict      ──► Streamlit UI
```

Intermediate artifacts are preserved in **`history[]`** for Audit Logs and Trace tab.

---

## How unsupported claims are caught

1. **Assessment prompt** requires corpus `chunk_id` on legal claims and upload IDs on facts.  
2. **Critic checklist** explicitly checks citation support and relevance.  
3. **Issues array** names claim + problem + severity (`citation`, `confidence`, `contradiction`, …).  
4. **Revision instruction** tells Assessment Agent what to fix (e.g. add Art. 6 cite, lower confidence).  
5. **Presenter warnings** surface critic fail, low confidence, GPAI flags to the user.  
6. **UI** separates **system inference** (agent conclusions) from **direct quotes** (citation cards).  

The Critic does **not** guarantee legal correctness — it enforces **process quality** (grounding, qualification, structure).

---

## How overconfidence is reduced

- Assessment prompt asks for **low** confidence when facts are missing.  
- Critic fails assessments with **high confidence + thin citations**.  
- Missing-information section and follow-up questions force explicit gaps.  
- Mock and live modes both expose **confidence** in risk hero and metrics.  
- Disclaimer on every report view.  

---

## ReAct inside Assessment (inner loop)

Separate from the Critic revision loop:

- If Assessment returns `needs_more_evidence: [queries…]`, it runs **extra retrieval** (max 2 iterations).  
- This is **evidence gathering**, not a separate agent.  

---

## Visibility in the UI

| UI location | What it shows |
|-------------|---------------|
| **Trace tab** | Full timeline + raw JSON per stage |
| **Audit Logs page** | Session-level stage summary |
| **Right column timeline** | Compact PASS / REVISE / DONE badges |
| **Status metric** | Critic Pass/Revise + Draft v1/v2 |

---

## Mock vs live

| Mode | Assessment | Critic |
|------|------------|--------|
| `MOCK_LLM=true` | Keyword → fixture JSON | Heuristic pass/fail |
| `MOCK_LLM=false` | Live LLM + ReAct | Live LLM checklist |

Pipeline shape is **identical** — judges can demo offline, then show live if API available.

---

## Related docs

- Agent schemas: [`../AGENTS.md`](../AGENTS.md)  
- Architecture: [`architecture.md`](architecture.md)  
- Citations: [`citation_and_evidence.md`](citation_and_evidence.md)  
- Demo script: [`demo_guide.md`](demo_guide.md)  
