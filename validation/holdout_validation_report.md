# Holdout Validation Report

Generated: 2026-05-23T22:46:04+00:00

## Scope

Public holdout validation on institutional mortgage performance data.
Not production validation. Not consumer credit eligibility. Not regulatory compliance proof.

## Pipeline validation vs outcome validation

- Pipeline validation: deterministic matured holdout split, CPD estimation on train rows only, holdout scoring, replay checks, and audit-chain verification.
- Outcome validation: measured AUC/PR-AUC/Brier/calibration/confusion on held-out rows with real outcome labels.

## Data used

- `validation/outputs/freddie_mac_normalized.50k.csv`
- `validation/outputs/fannie_mae_normalized.50k.csv`

HMDA is excluded from default-performance holdout evaluation and remains appropriate for fairness/decision-disparity diagnostics only.
CFPB complaint validation remains a separate complaint-governance pathway.

## Split design

- strategy: matured Freddie holdout by loan-age proxy
- matured threshold: `loan_age_months >= 24` for holdout cohort
- train rows: Freddie rows below threshold + all Fannie rows
- test rows: Freddie rows at/above threshold

Measured split counts:

- train_rows: 58,579
- test_rows: 41,421
- rejected_rows: 0
- Freddie train rows: 8,579
- Freddie test rows: 41,421
- Fannie train rows: 50,000

## Outcome definition

Binary outcome uses existing normalized mortgage proxy label:

- positive class: `risk = high_risk`
- negative class: `risk = low_risk`

This proxy is derived from mapped delinquency/default/loss indicators in the source preparation scripts.

## Event counts and prevalence

- train positives: 67
- train prevalence: 0.001144
- test positives: 201
- test prevalence: 0.004853

## Before vs after setup

Before:

- evidence features: `tenure, utilization`
- policy thresholds:
  - decline: `0.0041568`
  - review lower/upper: `0.004` / `0.0041568`

After:

- evidence features: `tenure, utilization, income, dsc`
- policy thresholds (calibrated on train rows only):
  - decline: `0.002232641215`
  - review lower/upper: `0.001556776557` / `0.002232641215`

## Before vs after measured results

Decision distribution (test):

- before: APPROVE 41,421 | REVIEW 0 | DECLINE 0
- after: APPROVE 36,336 | REVIEW 5,085 | DECLINE 0

Outcome metrics:

- AUC: before `0.538963` -> after `0.573062`
- PR-AUC: before `0.005601` -> after `0.006059`
- Brier: before `0.004842` -> after `0.004842`

Confusion highlights:

- before at decline threshold: TP 0 | FP 0 | TN 41,220 | FN 201
- after at manual-review lower threshold: TP 32 | FP 5,053 | TN 36,167 | FN 169

## Replay and audit integrity

- replay_success_rate: 1.0
- audit_chain_verification: true

## Guardrails

- minimum required test positives: 100
- observed test positives: 201
- underpowered outcome validation: false
- single decision class: false

## Interpretation

The holdout path is real and now produces non-single-class policy outcomes with modest discrimination improvement.
Signal remains weak overall and decline-threshold separation is still limited on this cohort.

## Limitations

- Holdout split uses loan-age proxy because exact lifecycle labels are limited in normalized files.
- Public institutional mappings remain proxy transformations into simplified causal states.
- Metrics remain modest; this is outcome validation evidence for governance workflow quality, not production readiness or regulatory compliance proof.
