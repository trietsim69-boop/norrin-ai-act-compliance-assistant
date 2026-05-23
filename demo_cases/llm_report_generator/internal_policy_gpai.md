# Internal Policy — Use of Third-Party LLM Tools

**Applies to:** InsightWriter and similar internal tools  
**Owner:** IT Governance

## Rules

1. Only approved GPAI providers may be used for production workloads.
2. Deployers must obtain and retain **provider compliance documentation** (model cards, prohibited use policies).
3. All **LLM-generated** outputs require human review before operational use.
4. Sensitive personal data must not be sent to external APIs without DPO approval.

## Roles

| Role | Responsibility |
|------|----------------|
| GPAI provider | Foundation model, Article 53 obligations |
| Our organisation (deployer) | Prompt design, data selection, human review, appropriate use |

## Open actions

- Collect signed Article 53 package from OpenAI-compatible vendor.
- Document review workflow and escalation when analyst rejects draft.
- Assess whether downstream HR use of reports triggers high-risk obligations.
