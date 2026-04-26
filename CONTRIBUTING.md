# Contributing

## Local setup

```bash
python -m venv .venv
```

Activate environment:

- Windows PowerShell: `.venv\\Scripts\\Activate.ps1`
- macOS/Linux: `source .venv/bin/activate`

Install dependencies:

```bash
pip install -e ".[dev]"
```

## Quality gate

Before proposing changes:

```bash
python -m pytest -q
python -m causal_credit_risk.cli --json-only
python -m causal_credit_risk.cli --replay-audit examples/audit_example.json
```

## Contribution rules

- Do not change CPD values or model semantics without explicit governance review.
- Keep behavior deterministic and test-backed.
- Preserve BUSL-1.1 language and governance warnings.
- Add or update docs for externally visible changes.

## Pull request expectations

- clear change summary
- tests demonstrating behavior
- risk/regression notes
- documentation updates for any user-facing behavior changes
