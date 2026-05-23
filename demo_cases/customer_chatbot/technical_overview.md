# SupportBot — Technical Overview

## Architecture

```
User → Web chat widget → API gateway → LLM inference → Response
                              ↓
                        Knowledge base (RAG)
```

## LLM usage

- Primary model: GPT-class **large language model** accessed through vendor API.
- Temperature capped at 0.3 for factual support answers.
- System prompt enforces brand tone and refusal of legal/medical advice.

## Data handling

- Chat transcripts retained 90 days for QA.
- No training on customer messages (contractual prohibition with LLM vendor).

## Monitoring

- Weekly review of failed conversations and user satisfaction scores.
- No dedicated human-in-the-loop during live chat unless user requests escalation.
