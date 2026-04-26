# Evidence Pack Workflow

## Purpose

Create a local governance evidence package from batch inputs.

## Command

```bash
python scripts/export_evidence_pack.py --input-csv examples/batch_with_segments.csv
```

## Default output

- `outputs/evidence_pack_<timestamp>/`

## Included artifacts

- batch decision output CSV
- fairness report JSON
- audit chain JSON
- audit chain verification JSON
- replay result JSON
- copied model and policy config files
- evidence-pack metadata JSON

## Governance note

Evidence packs support pilot governance review and traceability. They are not legal certification artifacts.
