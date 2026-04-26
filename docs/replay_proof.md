# Deterministic Replay Proof

This document describes how deterministic replay is validated.

## Baseline artifact

Use a saved audit record, for example:

- `examples/audit_example.json`

## Replay command

```bash
python -m causal_credit_risk.cli --replay-audit examples/audit_example.json
```

## Expected match behavior

Replay recomputes the decision against the active model and policy, then reports:

- `risk_probability_match: true`
- `decision_match: true`

when the active model/policy contract matches the audit metadata.

## Mismatch behavior

Replay fails cleanly when any of these differ:

- `model_id`
- `model_version`
- `policy_version`

This prevents false deterministic-match claims across incompatible runtime contracts.
