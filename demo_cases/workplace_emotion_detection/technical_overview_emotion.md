# MoodSense — Technical Overview (Procurement Pack)

## Inference pipeline

1. Capture video/audio stream from approved endpoints.
2. Pre-process frames; detect faces.
3. Run proprietary **affect classification model** (multi-class emotion labels).
4. Aggregate scores over time windows; push to manager dashboard API.

## Model outputs

- Primary labels: happy, neutral, stressed, frustrated, disengaged.
- Confidence score per inference.
- No raw video stored after 24 hours (vendor claim).

## Integration

- SSO with corporate identity provider.
- HRIS webhook for wellness programme enrolment triggers.

## Open technical questions

- Exact definition of "emotion" vs "attention" in model documentation.
- Whether inference runs on-premise or in vendor cloud (EU region stated but not verified).
