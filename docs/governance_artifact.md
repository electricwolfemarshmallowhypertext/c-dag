# Governance Artifact

C-DAG can emit a schema-backed governance artifact for each decision. The artifact is designed to make a decision replayable, inspectable, and suitable for internal model-risk, audit, engineering, and governance review.

The schema is defined at `schemas/governance-artifact.schema.json`.

## What the artifact contains

Each governance artifact includes:

* model version
* policy version
* deployment version and model lifecycle metadata
* input evidence
* inferred nodes
* risk probability
* decision
* causal chain
* counterfactuals
* replay hash
* audit-chain hash
* validation status
* timestamp
* boundary metadata
* optional control references
* optional human review fields

Optional human review fields are:

* reviewer_id
* review_status: pending, approved, rejected, or escalated
* review_notes
* reviewed_at
* review_history

## Workflow

1. Generate a decision through the CLI or API.
2. Export the governance artifact.
3. Replay-verify the artifact against the active model and policy configuration.
4. Map the artifact to configured control frameworks when a compliance-support package is needed.
5. Include the artifact, replay result, audit-chain verification, control mappings, model and policy metadata, and available fairness diagnostics in an evidence pack.
6. Add human review metadata when a reviewer evaluates the artifact.

## CLI

```bash
python -m causal_credit_risk.cli --export-governance-artifact ./artifact.json

python -m causal_credit_risk.cli --replay-governance-artifact ./artifact.json
```

Replay verification reports:

* replay_match
* model_version_match
* policy_version_match
* hash_match
* validation_status

## API

`POST /v1/decision` returns the existing decision response shape and adds a `governance_artifact` field.

Review and compliance-support endpoints are documented in `docs/compliance_support.md`.

## Boundaries

C-DAG is not a standalone production lending decision engine and does not independently determine consumer credit eligibility. It produces replayable governance evidence for teams evaluating, validating, auditing, or overseeing high-risk credit-decision systems.

C-DAG does not:

* serve as standalone production lending adjudication
* independently determine consumer credit eligibility
* certify regulatory compliance
* provide legal advice
* replace institutional governance programs
* replace human review or approval
* guarantee fairness or regulatory acceptance
