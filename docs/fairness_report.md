# Fairness Report

This package includes lightweight subgroup fairness diagnostics for batch outputs.

## Important warning

This report is a diagnostics artifact, not fairness certification.

It cannot by itself establish legal or policy compliance. Real fairness evaluation requires domain, legal, and statistical review.

## Inputs

The fairness utility expects batch-style decision rows with:

- `decision` and `risk_probability` fields, or
- `audit` object containing these fields

Optional:

- subgroup column (default: `segment`)

## Output metrics

The report includes:

- row counts by subgroup
- approval/review/decline rates by subgroup
- mean risk probability by subgroup
- max/min subgroup deltas across key rates
- warnings when subgroup sample size is below threshold

## Suggested usage

- Use diagnostics during development and governance reviews.
- Flag subgroup disparities for deeper investigation.
- Pair this report with richer fairness methods before deployment decisions.
