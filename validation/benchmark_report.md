# C-DAG Benchmark / Evidence Dashboard Report

Generated: 2026-06-09

## Scope

This report packages measured C-DAG public validation evidence into one benchmark artifact.
It answers what C-DAG actually ran, what verified, what failed, and what remains bounded.

This is a workflow evidence benchmark, not production validation, not a lending decision system, not customer-data validation, and not proof of regulatory compliance.

## Validation coverage

Measured or parsed repository evidence:

- public financial rows processed: `100k+`
- validation lanes: `6`
- file corpus inspected: `117`
- usable structured candidates: `102`
- file inventory:
  - loan-level validation data: `101`
  - cohort/aggregate validation data: `1`
  - dashboard exports: `9`
  - schema/header/glossary files: `1`
  - unsupported files: `5`

Public data domains covered:

- mortgage performance
- mortgage applications
- consumer complaints
- CRT
- CAS
- public loss-exposure records

## Validation lanes

| Lane | Rows | Measured result |
| --- | ---: | --- |
| Freddie + Fannie + HMDA | 30,000 | APPROVE 9,584 / REVIEW 4,368 / DECLINE 16,048 |
| CFPB complaints | 10,000 | APPROVE 0 / REVIEW 9,837 / DECLINE 163 |
| Freddie/STACR CRT | 10,000 | APPROVE 9,299 / REVIEW 0 / DECLINE 701 |
| Fannie CAS April 2026 | 10,000 | APPROVE 7,948 / REVIEW 686 / DECLINE 1,366 |
| Baseline outcome holdout | train 58,579 / test 41,421 | AUC 0.573062 / PR-AUC 0.006059 |

## Replay verification

Dashboard wording:

> 100% replay success on sampled validation audit records.

Verified in validation reports:

- public mortgage validation reports replay success as `1.0`
- CFPB complaint validation reports replay success as `1.0`
- CRT/STACR validation reports replay success as `1.0`
- CAS validation reports replay success as `1.0`
- mortgage holdout validation reports replay success as `1.0`

TODO:

- Record sampled replay audit count consistently across every validation report.

## Audit-chain integrity

Verified in validation reports:

- audit-chain verification reported as `true` across reported validation runs

Verified in tests:

- valid chain passes
- modified audit record fails hash verification
- modified chain fails chain verification

TODO:

- Record audit-chain record count consistently across every validation report.

## Performance benchmark

Timing metrics are not currently measured consistently enough to report.

TODO:

- Add measured batch throughput timing.
- Add measured evidence-pack generation timing.
- Add measured validation run duration.

## Loss exposure mapping

Parsed public-record pack:

- records parsed: `5`
- sources present: CFPB, FINRA, SEC, OCC, AI operational-loss research
- source not yet parsed from local record corpus: FFIEC

| Public record | Public exposure amount | Failure type | Missing evidence artifact | C-DAG artifact fit |
| --- | --- | --- | --- | --- |
| CFPB / Wells Fargo $3.7B order | $3.7B | Consumer-harm and servicing-control breakdown | Cross-workflow replayable decision trace | trace, counterfactual, replay, hash-chain, evidence pack, risk-exposure mapping |
| FINRA 2025 recurring fine categories | not specified | Control, supervision, and record-integrity gaps | Tamper-evident control evidence | replay, hash-chain, evidence pack, risk-exposure mapping |
| SEC AI-washing enforcement focus | not specified | Governance and disclosure mismatch | Trace-backed governance documentation | trace, counterfactual, replay, evidence pack, risk-exposure mapping |
| AI operational-loss research in U.S. BHCs | not specified | Operational-risk exposure growth | Pre-escalation decision evidence | trace, replay, hash-chain, risk-exposure mapping |
| OCC Spring 2025 risk framing | not specified | Model, cybersecurity, and compliance-control gaps | Integrated decision-level audit trail | trace, replay, hash-chain, evidence pack, risk-exposure mapping |

Boundary:

C-DAG does not prove prevention or savings. It demonstrates how high-risk financial decisions can be made replayable, inspectable, and auditable before issues escalate.

## Holdout baseline

Measured baseline outcome holdout:

- train rows: `58,579`
- test rows: `41,421`
- test positives: `201`
- AUC: `0.573062`
- PR-AUC: `0.006059`
- decision distribution: APPROVE `36,336` / REVIEW `5,085` / DECLINE `0`

Limitation:

This is baseline outcome validation, not production model performance.

## Dashboard data source

Dashboard metrics are stored in:

- `validation/benchmark_metrics.json`

Dashboard page:

- `site/benchmark.html`

## TODO summary

- Record sampled replay audit count consistently across every validation report.
- Record audit-chain record count consistently across every validation report.
- Add measured batch throughput timing.
- Add measured evidence-pack generation timing.
- Add measured validation run duration.
- Parse an FFIEC public record if included in the local public-record corpus.
