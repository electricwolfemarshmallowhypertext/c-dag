# Opaque Mortgage Benchmark Report

Generated: 2026-07-07T22:39:06+00:00

## Scope

Real opaque-model benchmark on normalized public mortgage rows.
This is validated surrogate governance evidence, not automatic causal truth.

The benchmark trains a deterministic opaque stump ensemble on normalized mortgage risk-state fields, then fits a linear surrogate to the opaque model's behavior and evaluates surrogate fidelity, stability, proxy flags, and counterfactual consistency.

## Data

- inputs: `validation/outputs/freddie_mac_normalized.50k.csv`, `validation/outputs/fannie_mae_normalized.50k.csv`
- rows_loaded: 236,139
- train_rows: 165,297
- test_rows: 70,842
- positive test outcomes: 188
- test prevalence: 0.004633

## Feature policy

Mapped mortgage fields now include:

- LTV risk
- CLTV risk
- DTI risk
- FICO risk
- loan-age risk
- delinquency-history risk
- occupancy risk
- loan-purpose risk
- property-type risk
- modification risk
- default/loss risk

The opaque predictive benchmark excludes leakage-prone fields that may directly encode the outcome label:

- delinquency-history risk
- modification risk
- default/loss risk

Benchmark features used:

- LTV risk
- CLTV risk
- DTI risk
- FICO risk
- loan-age risk
- occupancy risk
- loan-purpose risk
- property-type risk

## Opaque model outcome metrics

- opaque model type: deterministic stump ensemble
- AUC: 0.646938
- PR-AUC: 0.005352
- Brier score: 0.002646

These metrics are above the previous weak causal holdout baseline, but they remain modest. This benchmark should not be described as strong production predictive performance.

## Surrogate governance metrics

- approximation label: high_fidelity_surrogate
- mean absolute error: 0.000000
- root mean squared error: 0.000000
- max absolute error: 0.000000
- classification agreement: 1.000000
- stable surrogate drivers: FICO risk, loan-age risk, CLTV risk, LTV risk
- counterfactual consistency label: counterfactual_direction_consistent
- counterfactual sign agreement rate: 0.750000
- proxy findings: 0

## Extracted surrogate pathway

Top surrogate associations with opaque model score:

- FICO risk: 0.812429
- loan-age risk: 0.576236

## Interpretation

The opaque benchmark now provides real surrogate-governance evidence on public mortgage rows.
It shows that the surrogate can closely approximate this deterministic opaque benchmark model's scores.
It does not show that the extracted graph is the true causal graph.

The predictive signal remains limited. The current result supports auditability and replayable surrogate evidence more strongly than production-grade risk prediction.

## Boundary

Public reference validation only.
No customer-data evaluation.
Not live lending decision software.
Not a legal or regulatory certification.
No guaranteed financial outcome.

