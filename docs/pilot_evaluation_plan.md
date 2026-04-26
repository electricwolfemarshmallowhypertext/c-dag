# Pilot Evaluation Plan

## Duration

2 to 4 weeks.

## Pilot structure

1. Week 1: environment setup, config review, demo baseline.
2. Week 2: batch/replay/fairness workflow validation.
3. Week 3: governance evidence-pack review with model-risk/compliance.
4. Optional Week 4: integration readiness decision.

## Success criteria

- Deterministic replay passes for selected decisions.
- Batch workflow produces row-level explainability artifacts.
- Fairness diagnostics generate subgroup metrics and warnings.
- Audit chain verification detects tampering.
- Governance teams can review artifacts without code changes.

## Technical validation

- API and CLI parity checks.
- Input validation failure-path checks.
- Config/version contract checks.
- Smoke tests and unit tests reviewed.

## Governance validation

- Model and policy version traceability.
- Counterfactual interpretability review.
- Audit artifact completeness review.
- Limitations and prohibited-use acknowledgment.

## Sample artifacts delivered

- Decision audit JSON
- Replay result JSON
- Fairness report JSON
- Audit chain JSON + verification result
- Evidence-pack metadata manifest

## Out of scope

- Legal sign-off
- Production credit policy approval
- Fairness certification
- Hosted infrastructure and SSO rollout

## Decision criteria for paid license

- Pilot success criteria met.
- Integration scope agreed.
- Commercial terms and support boundary accepted.
