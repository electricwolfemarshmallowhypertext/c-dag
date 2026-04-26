# Integration Boundaries

## What the engine does

- Loads versioned causal model and policy config.
- Runs exact discrete DAG inference.
- Produces decision/audit/counterfactual outputs.
- Supports deterministic replay and batch processing.
- Generates fairness diagnostics and audit-chain records.

## What the engine does not do

- Train production credit models.
- Approve lending policy.
- Provide legal or regulatory certification.
- Provide hosted multi-tenant infrastructure.

## Where auth belongs

Deployment boundary controls (gateway, service mesh, enterprise IAM).

## Where storage belongs

Governed artifact stores and enterprise databases. Local file/SQLite stores are seam defaults only.

## Where model governance belongs

Formal model-risk lifecycle controls outside this package (review, approval, monitoring, retirement).

## MRM/compliance integration path

1. Generate audit artifacts per decision.
2. Store artifacts in governed repositories.
3. Validate replay determinism and policy contracts.
4. Attach artifacts to internal audit or regulator response workflows.
