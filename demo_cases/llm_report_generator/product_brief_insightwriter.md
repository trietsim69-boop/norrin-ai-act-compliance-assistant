# InsightWriter — Internal Report Generator (Product Brief)

**Team:** Business Intelligence  
**Status:** Internal beta

InsightWriter is an internal tool that uses a **third-party GPT API** to generate narrative business reports from structured sales and operations data.

## Workflow

1. Analyst selects data sources and report template (weekly sales, pipeline review).
2. Tool sends structured JSON summaries to the **large language model** via API.
3. **LLM** returns a draft report in natural language.
4. Analyst reviews and edits before distribution to leadership.

## GPAI dependency

- Model: commercial GPT-class API (provider hosts foundation model).
- Our organisation acts as **deployer** — we define prompts, data inputs, and review outputs.
- No fine-tuning on proprietary data in current beta.

## Use cases

- Internal management reporting only (not customer-facing).
- Reports may inform staffing decisions but are not sole basis for HR actions.

## Compliance gaps

- Article 53 provider documentation not yet collected from vendor.
- Labelling of AI-generated report sections not implemented.
