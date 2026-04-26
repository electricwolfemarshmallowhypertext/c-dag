# Release Notes v0.2.0

Date: 2026-04-26

## Included in this release

- API surface for health, readiness, decision, replay, batch, fairness, and audit-chain verification.
- Deterministic replay contract checks for model/policy version consistency.
- CSV batch mode with row-level success/error outputs.
- Fairness diagnostics for subgroup metrics and small-sample warnings.
- Tamper-evident audit hash-chain generation and verification.
- Enterprise/pilot documentation set for governance workflows.

## Known limitations

- Not a production lending model.
- Not fairness-certified.
- Not legal/compliance certification.
- Not bundled with enterprise IAM or hosted infrastructure.

## Invariants preserved

- Core inference math unchanged.
- CPD values unchanged.
- Model semantics unchanged.
- Default decision risk output remains `0.849375`.
