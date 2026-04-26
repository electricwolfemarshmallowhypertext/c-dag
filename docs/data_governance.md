# Data Governance

## Config-driven CPDs

Model structure and CPDs are loaded from versioned config files.

- `configs/credit_risk_model.v1.json`
- `configs/decision_policy.v1.json`

## Demo versus production

The bundled CPDs are illustrative and for explainability demonstrations only.

Real CPDs must be:

- estimated from validated portfolio data
- reviewed by domain experts
- independently validated
- approved through model-risk governance
- versioned with change control
- monitored after deployment

## Required governance controls

- formal data lineage documentation
- reproducible data preparation
- periodic recalibration review
- exception management and incident workflows
- documented approval records for each model/policy release
