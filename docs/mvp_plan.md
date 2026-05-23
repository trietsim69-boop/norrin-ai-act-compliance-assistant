# MVP plan — Norrin AI Act Compliance Assistant

High-level product plan for the hackathon MVP. **Implementation status:** steps 1–12 complete — see [`codebase_status.md`](codebase_status.md).

---

## Goal

Give compliance and product teams a **first-pass, citation-backed** read on whether a single AI use case may trigger EU AI Act concerns — with clear uncertainty, missing-info prompts, and **no claim of final legal advice**.

---

## Core requirements

1. **One use case per session** — multiple documents, one assessment narrative  
2. **Built-in legal corpus** — EU AI Act + official Commission guidance, retrieved not pasted  
3. **Uploaded evidence separation** — user facts vs regulatory references  
4. **Multi-agent review** — assess, critique, revise once, present  
5. **Transparent output** — agent history, critic verdict, citations, confidence  
6. **Offline demo path** — mock LLM for judges when API unavailable  

---

## MVP features (included)

| Feature | Description |
|---------|-------------|
| Document upload | PDF, DOCX, PPTX, HTML, CSV, TXT, MD via MarkItDown |
| Manual description | Run assessment without files |
| Session metadata | Case name, sector, role, deployment context |
| RAG retrieval | Dual Chroma collections (uploads + corpus) |
| Assessment Agent | Structured JSON assessment with citations |
| Critic Agent | Pass/fail + revision instruction |
| One revision loop | Assessment v2 + Critic v2 when needed |
| Presenter | Deterministic dashboard formatting |
| Citation resolver | Readable source labels from chunk IDs |
| Streamlit console | Intake, tabbed report, sidebar, nav pages, agent trace |
| Follow-up / Reassess | Missing-info tab; re-run pipeline on same session |
| Demo cases | Five evaluation paths + trigger tests |
| Export Brief | JSON download of assessment payload |

---

## Intentionally not included

- Final legal opinions or filing-ready compliance sign-off  
- Multi-tenant auth, billing, or enterprise RBAC  
- Full EUR-Lex navigation UI (corpus is pre-indexed, not browsable article-by-article in MVP)  
- Unlimited critic/assessment loops (capped at **one** revision)  
- Automated enforcement or blocking of deployments  
- Guaranteed real-LLM accuracy on all edge cases without human review  

---

## Future improvements

- Cleaner citation “surrounding passage” (section-aware chunks)  
- PDF/Markdown export of full report  
- Additional demo paths (e.g. industrial predictive maintenance as first-class fixture)  
- Real-LLM regression suite in CI  
- Scope gate for malicious or clearly out-of-scope prompts  
- Streamlit Cloud / container deployment  
- Optional OpenAI embeddings at scale  

---

## Success criteria (hackathon)

- Demonstrates **regulatory grounding** via corpus RAG + citation cards  
- Demonstrates **multi-agent design** with visible stages and revision  
- Usable **UX** for upload → report → trace → citations  
- Honest **uncertainty** and missing-info handling  
- Repeatable **demo cases** and trigger tests  

---

## Related docs

- Architecture: [`architecture.md`](architecture.md)  
- Multi-agent: [`multi_agent_pipeline.md`](multi_agent_pipeline.md)  
- Setup: [`setup_and_run.md`](setup_and_run.md)  
- Demo: [`demo_guide.md`](demo_guide.md)  
