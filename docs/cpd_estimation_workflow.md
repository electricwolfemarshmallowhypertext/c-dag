# CPD Estimation Workflow

## Purpose

Generate draft CPDs from categorical CSV data for review workflows.

## Command

```bash
python scripts/estimate_cpds_from_csv.py --input-csv ./data.csv --output ./models/draft/draft_model.json --source-dataset-reference pilot_dataset_v1
```

## Output guarantees

- Output is marked `approval_status: draft`
- Includes `generated_at_utc`, dataset reference, estimator version, and review note
- Does not overwrite existing output unless `--force` is supplied

## Governance warning

Estimated CPDs are not auto-approved. Domain expert and model-risk review are required before any operational use.
