# Industrial predictive maintenance — demo case for citation correctness tests

## System overview

**Product name:** MachineGuard PM  
**Vendor:** Norrin Industrial Analytics GmbH

## Purpose

MachineGuard PM monitors vibration and temperature sensors on factory machinery (pumps, compressors, conveyor motors). A custom **LSTM neural network** trained on historical sensor logs predicts component failures 48–72 hours before they occur.

Maintenance technicians receive alerts in a dashboard. They schedule inspections manually — the system does **not** autonomously shut down equipment or make hiring, credit, or safety-critical product decisions.

## Technical architecture

- **Model:** Proprietary LSTM (PyTorch), trained in-house on client sensor data
- **Not a foundation model** — no third-party LLM or GPAI component
- **Inputs:** IoT sensor streams (vibration, temperature, RPM)
- **Outputs:** Failure probability score and recommended inspection window
- **Deployment:** On-premise edge server at the factory; no cloud inference for production alerts

## Who uses the system

- **Maintenance technicians** who act on alerts
- **No direct impact on job applicants or end consumers**
- No profiling of individuals

## Sector

Industrial manufacturing / predictive maintenance

## Human oversight

Technicians review every alert before scheduling maintenance. The model does not control machinery directly.

## What this system is NOT

- Not used for HR or personnel evaluation workflows
- Not integrated as a safety component of a regulated product (e.g. medical device, automotive ECU)
- Not a general-purpose AI model or chatbot

## Open questions

- Whether the AI is embedded as a **safety component** under Article 6(1) is **unclear** from current documentation
- Deployment geography and scale are not specified
