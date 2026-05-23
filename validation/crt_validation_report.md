# Public CRT Loan-Level Validation Report

Generated: 2026-05-23T15:17:17+00:00

## Non-production disclaimer

Public CRT loan-level validation. Not production validation, not consumer credit eligibility, and not regulatory compliance proof.

## Input scope used in this run

- Validation source directory inspected: `docs/new/CRT`
- Data type used: headerless, pipe-delimited `*_lld` loan-level text files
- Pilot input file used for measured run: `24DNA2_20260501_lld.txt`
- Prep path used: `scripts/prepare_freddie_stacr.py`
- CAS prep path (`scripts/prepare_fannie_cas.py`) was not used for this measured run because no clearly matching loan-level CAS dataset file was used from `docs/new/CRT`.

## Schema/layout checks before run

- First-row field count check (`24DNA2_20260501_lld.txt`): `90`
- First-row field count check (`25SPH1_20260501_lld.txt`): `90`
- Layout treated as Freddie-style CRT loan-level disclosure format for preprocessing.

## Measured run configuration

- Prepare command: `python scripts/prepare_freddie_stacr.py --input docs/new/CRT/24DNA2_20260501_lld.txt --output validation/outputs/freddie_stacr_normalized.24DNA2.10k.csv --max-rows 10000`
- Validation command: `python scripts/run_crt_validation.py --input validation/outputs/freddie_stacr_normalized.24DNA2.10k.csv --model-config configs/public_crt_model.v1.json --policy-config configs/public_crt_policy.v1.json --output-dir validation/outputs/crt_validation_real --max-audits 50 --evidence-pack-max-rows 1000`

## Rows processed

- rows_processed: `10,000`
- accepted_rows: `10,000`
- rejected_rows: `0`

## Dataset source

- `freddie_mac_stacr_loan_level`

## Mapped fields

- `source_dataset`
- `source_record_id`
- `leverage_risk`
- `borrower_credit_risk`
- `loan_performance_risk`
- `property_or_pool_segment`
- `delinquency_or_loss_proxy`
- `crt_escalation_risk`
- `segment`

## Decision distribution

- APPROVE: `9,299`
- REVIEW: `0`
- DECLINE: `701`
- error: `0`

## Replay and audit integrity

- replay_success_rate: `1.0`
- audit_chain_verification: `true`

## Sampled evidence pack

- evidence_pack_mode: `sampled`
- sampled_rows: `1,000`

## Fairness/segment diagnostics (run summary)

- subgroup_column: `segment`
- rows_analyzed: `10,000`
- max/min subgroup deltas:
  - mean_risk_probability_delta: `0.1985138`
  - approve_rate_delta: `0.2`
  - decline_rate_delta: `0.2`
- warnings: small-sample subgroup warnings present (10 groups below minimum sample threshold).

## Limitations

- Mapping from `*_lld` fields into C-DAG CRT states is proxy-based and not equivalent to underwriting truth labels.
- This run uses one real `*_lld` file capped at 10k rows as a pilot validation pass.
- Results are for explainability/governance validation and replayability checks only.
