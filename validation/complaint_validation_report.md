# Public CFPB Complaint-Data Validation Report

Generated: 2026-05-19T23:50:15+00:00

## Non-production disclaimer

This is **public CFPB complaint-data validation**. It is not production validation, not credit scoring, not credit-eligibility decisioning, and not proof of regulatory compliance.

## Validation scope

- Dataset family: CFPB Consumer Complaint Database (public)
- Validation objective: complaint-risk / escalation governance auditability
- Core outputs: batch decisions, audit traces, deterministic replay checks, audit-chain verification, segment-level fairness diagnostics

## Normalized governance variables

- `product_risk`
- `issue_complexity`
- `company_response_quality`
- `timely_response`
- `consumer_disputed`
- `escalation_risk`
- `segment`

## 1k run (required first pass)

Command path:

- `prepare_cfpb_complaints.py --max-rows 1000`
- `run_cfpb_complaint_validation.py --max-audits 50`

Measured results:

- rows_processed: `1,000`
- accepted_rows: `1,000`
- rejected_rows: `0`
- decision_distribution:
  - APPROVE: `486`
  - REVIEW: `504`
  - DECLINE: `10`
  - error: `0`
- replay_success_rate: `1.0`
- audit_chain_verification: `true`
- fairness rows analyzed: `1,000`
- fairness warnings: `41` (small-sample segment warnings present)

## 10k run (performed because runtime was fast)

Command path:

- `prepare_cfpb_complaints.py --max-rows 10000`
- `run_cfpb_complaint_validation.py --max-audits 50`

Measured results:

- rows_processed: `10,000`
- accepted_rows: `10,000`
- rejected_rows: `0`
- decision_distribution:
  - APPROVE: `0`
  - REVIEW: `9,837`
  - DECLINE: `163`
  - error: `0`
- replay_success_rate: `1.0`
- audit_chain_verification: `true`
- fairness rows analyzed: `10,000`
- fairness warnings: `20`

## Field mapping assumptions

- `product_risk` derived from complaint `Product` categories.
- `issue_complexity` derived from `Issue`, `Sub-issue`, and narrative presence/keywords.
- `company_response_quality` derived from `Company response to consumer`.
- `timely_response` derived from `Timely response?`.
- `consumer_disputed` derived from `Consumer disputed?`.
- `escalation_risk` is a proxy derived from timeliness, dispute status, response quality, and product-risk context.
- `segment` derived from `State`.

## Limitations

- Escalation risk is a proxy governance signal, not a legal outcome classification.
- Mapping logic is heuristic and requires domain-review calibration before operational use.
- This validation does not establish production readiness or regulatory sufficiency.
