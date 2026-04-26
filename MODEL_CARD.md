# Model Card: causal-credit-risk-engine

## Model identity

- Model ID: `credit_risk_causal_dag`
- Model version: `1.0.0`
- Model class: discrete causal DAG with exact inference
- Intended package: `causal-credit-risk-engine`

## Intended use

This model is intended for explainability demonstrations, governance workflow prototyping, and audit-trace reproducibility exercises.

## Intended users

- model-risk teams
- compliance and governance analysts
- internal audit and control functions
- technical teams building explainability prototypes

## Prohibited uses

- real lending decisions
- credit eligibility decisions
- automated adverse action decisions
- any production decisioning without approved validation and governance

## Assumptions

- node states and causal structure are represented correctly for demo purposes
- CPDs are illustrative and not empirically calibrated to a production portfolio
- decision policy is a governance demo artifact, not institutional credit policy

## Inputs and outputs

- Inputs: observed evidence for configured observed nodes (for example `tenure`, `utilization`)
- Intermediate outputs: inferred node posteriors (for example `income`, `dsc`)
- Primary output: probability of `risk=high_risk`
- Policy output: `APPROVE`, `REVIEW`, `DECLINE`
- Audit output: structured decision trace with counterfactual evidence

## Validation evidence

Current automated validation includes:

- CPD shape, bounds, normalization checks
- node reference and DAG acyclicity checks
- policy threshold and policy/model reference checks
- deterministic replay checks
- API surface tests
- audit hash-chain integrity tests
- subgroup fairness diagnostics tests

## Known failure modes

- invalid or unsupported evidence states
- malformed batch records
- model/policy version mismatch during replay
- small-sample subgroup diagnostics instability

## Limitations

- toy-sized CPDs and graph
- no empirical portfolio calibration
- no fairness certification
- no production auth, tenancy, or secret management controls
- no legal/regulatory approval artifact set

## Required human oversight

- human review is required before any operational use
- model-risk and compliance approval are required before deployment
- fairness and legal review are required before production decisions

## Required real-world validation before deployment

Before any production use, require:

- validated portfolio dataset alignment
- calibration and stress testing
- fairness and subgroup impact analysis
- legal and policy review
- change-control and model-risk committee approval
- monitoring, incident response, and retirement criteria

## Causal structure

```text
Employment Tenure -> Income Stability -> Debt Service Coverage -> Default Risk Tier
Credit Utilization ----------------------------------------------> Default Risk Tier
```

All node metadata and CPDs are stored in versioned config files:

- `configs/credit_risk_model.v1.json`
- `configs/decision_policy.v1.json`

## Governance and licensing status

- License: Business Source License 1.1 (source-available, not OSI open-source)
- Commercial production use requires written permission
- This model card does not constitute legal advice or regulatory approval
