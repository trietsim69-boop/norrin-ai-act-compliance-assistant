# MailGuard — Technical Overview

## Classifier

- Gradient-boosted model + heuristic rules.
- Trained on labelled spam/ham corpus (no generative AI / **no LLM**).
- Updates via weekly signature and model refresh from vendor.

## Processing flow

```
SMTP inbound → MailGuard scan → score → quarantine or deliver
```

## Human oversight

- Users retrieve false positives from quarantine folder.
- Admin console allows threshold adjustment per domain.

## Good practice

- Monitor false-positive rate.
- Log quarantine decisions for audit.
- No personal profiling beyond message metadata.
