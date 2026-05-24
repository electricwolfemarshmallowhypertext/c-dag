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

## Fannie CAS April 2026 validation

Public CRT loan-level validation run from local CAS April 2026 files.
Not production validation, not consumer credit eligibility, and not regulatory compliance proof.

### CAS input and schema used

- Data file: `docs/new/CAS APRIL 2026/CAS_Apr26.csv`
- Header schema file: `docs/new/CAS APRIL 2026/CAS_Header_File.csv`
- Data layout: headerless pipe-delimited rows (`113` fields)
- Header layout: separate comma-delimited CAS header labels (`113` columns)
- Prep path used: `scripts/prepare_fannie_cas.py` with `--header-file` and `--delimiter "|"`

### CAS measured run configuration

- Prepare command: `python scripts/prepare_fannie_cas.py --input "docs/new/CAS APRIL 2026/CAS_Apr26.csv" --header-file "docs/new/CAS APRIL 2026/CAS_Header_File.csv" --delimiter "|" --output "validation/outputs/fannie_cas_normalized.april2026.10k.csv" --max-rows 10000`
- Baseline command (before calibration): `python scripts/run_crt_validation.py --input validation/outputs/fannie_cas_normalized.april2026.10k.csv --model-config configs/public_crt_model.v1.json --policy-config configs/public_crt_policy.v1.json --output-dir validation/outputs/cas_validation_april2026_10k --max-audits 50 --evidence-pack-max-rows 1000`
- Calibrated command (CAS policy): `python scripts/run_crt_validation.py --input validation/outputs/fannie_cas_normalized.april2026.10k.csv --model-config configs/public_crt_model.v1.json --policy-config configs/public_cas_policy.v1.json --output-dir validation/outputs/cas_validation_april2026_10k_calibrated --max-audits 50 --evidence-pack-max-rows 1000`
- CAS policy config: `configs/public_cas_policy.v1.json` (quantile-style thresholds from observed CAS risk score distribution)

### CAS measured results

- rows_processed: `10,000`
- accepted_rows: `10,000`
- rejected_rows: `0`
- dataset source: `fannie_mae_cas_loan_level`

Mapped fields:

- `source_dataset`
- `source_record_id`
- `leverage_risk`
- `borrower_credit_risk`
- `loan_performance_risk`
- `property_or_pool_segment`
- `delinquency_or_loss_proxy`
- `crt_escalation_risk`
- `segment`

Decision distribution:

- before calibration: APPROVE `0` | REVIEW `0` | DECLINE `10,000` | error `0`
- after calibration: APPROVE `7,948` | REVIEW `686` | DECLINE `1,366` | error `0`

Replay and audit integrity:

- before calibration replay_success_rate: `1.0`
- before calibration audit_chain_verification: `true`
- after calibration replay_success_rate: `1.0`
- after calibration audit_chain_verification: `true`

Evidence pack:

- evidence_pack_mode: `sampled`
- sampled_rows: `1,000`

CAS limitations:

- CAS April 2026 mapping is proxy-based from loan-level disclosure fields into CRT causal states.
- This run is a 10k capped pass for governance/audit-trace validation and does not establish production predictive validity.

## Additional intake-corpus measured runs (Worker 2)

These runs were executed against additional structured candidates discovered in `docs/new/`, without overwriting prior measured outputs.

### Freddie/STACR additional run (26DNA2)

- prep input: `docs/new/CRT/26DNA2_20260501_lld.txt`
- normalized output: `validation/outputs/freddie_stacr_normalized.26DNA2.10k.csv`
- validation output dir: `validation/outputs/crt_validation_26DNA2_10k`
- rows_processed: `10,000`
- accepted_rows: `10,000`
- rejected_rows: `0`
- decision distribution: APPROVE `9,420` | REVIEW `0` | DECLINE `580` | error `0`
- replay_success_rate: `1.0`
- audit_chain_verification: `true`
- evidence_pack_mode: `sampled` (`1,000` rows)

### Fannie CAS ZIP-path additional run (calibrated policy)

- prep input: `docs/new/CAS APRIL 2026/CAS_Apr26.zip` (member: `CAS_Apr26.csv`)
- header file: `docs/new/CAS APRIL 2026/CAS_Header_File.csv`
- normalized output: `validation/outputs/fannie_cas_normalized.april2026.zip.10k.csv`
- validation output dir: `validation/outputs/cas_validation_april2026_zip_10k_calibrated`
- policy config: `configs/public_cas_policy.v1.json`
- rows_processed: `10,000`
- accepted_rows: `10,000`
- rejected_rows: `0`
- decision distribution: APPROVE `7,948` | REVIEW `686` | DECLINE `1,366` | error `0`
- replay_success_rate: `1.0`
- audit_chain_verification: `true`
- evidence_pack_mode: `sampled` (`1,000` rows)

### Intake rejection notes for structured-but-non-usable files

- Short-width `*_lld` files with `4` fields on first row (for example `15SC02_20260501_lld.txt`) were rejected for loan-level validation because current CRT mappers require full-width disclosure layout.
- `docs/new/DEAL-RELATIVE-PROFILE-COMPARISON_Profile_data.csv` was classified as cohort/aggregate context data and not used as primary loan-level validation input.
