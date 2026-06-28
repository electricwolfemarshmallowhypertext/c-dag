# Compliance Support

C-DAG produces evidence that supports governance, model risk management, internal audit, and regulatory compliance workflows.

It does not certify regulatory compliance, provide legal advice, indicate regulator approval, or guarantee compliance.

## Supported Frameworks

The versioned control registry is defined at `configs/control_frameworks.v1.json`.

The default registry includes mapping support for:

* NIST AI RMF
* ISO/IEC 42001
* SR 11-7 Model Risk Management
* EU AI Act high-risk obligations
* Internal custom controls

## Control Mapping Model

Control mappings are configuration-driven. Each control declares evidence fields that a governance artifact may satisfy.

The mapping engine returns deterministic status values:

* `supported`: all configured evidence fields are present
* `partial`: some configured evidence fields are present
* `not_supported`: no configured evidence fields are present

Example mapping:

```json
{
  "id": "SR11-7-TRACE",
  "status": "supported",
  "evidence": ["replay_hash", "audit_chain", "model_version"]
}
```

## Governance Workflow

The compliance-support workflow is:

1. Generate a decision.
2. Emit a governance artifact.
3. Map the artifact to configured controls.
4. Replay-verify the artifact.
5. Verify audit-chain integrity.
6. Attach review history when reviewers assign, approve, reject, or escalate a case.
7. Export a compliance-support package for retention or transfer.
8. Import the package and verify stable integrity hashes before replay.

Review workflow fields are persisted in the governance artifact:

* reviewer_id
* review_status: pending, approved, rejected, or escalated
* review_notes
* reviewed_at
* review_history

## Evidence Lifecycle

Compliance-support packages include:

* governance artifact JSON
* replay verification result
* audit-chain verification result
* fairness report when available
* model metadata
* policy metadata
* control mappings
* evidence manifest
* integrity hashes
* model and policy configuration copies

Package exports use deterministic JSON formatting and stable content hashes. Restored packages can be checked for integrity and replay-verified against the referenced model and policy configuration.

## CLI

```bash
python -m causal_credit_risk.cli --export-compliance-package ./compliance_package

python -m causal_credit_risk.cli --import-compliance-package ./compliance_package
```

## API

Compliance-support endpoints:

* `GET /v1/control-frameworks`
* `GET /v1/control-mappings`
* `POST /v1/compliance-package`
* `POST /v1/review`

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
