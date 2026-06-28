# C-DAG

**Replayable causal audit traces for high-risk AI decisions.**

C-DAG transforms AI decisions into replayable, inspectable, and verifiable audit artifacts for governance, compliance, and model-risk workflows.

Instead of treating AI output as a black box, C-DAG records how a decision was reached, allows deterministic replay, generates counterfactual explanations, and produces tamper-evident audit evidence.

---

## Why C-DAG?

High-risk AI systems increasingly require more than a prediction.

Teams need to answer:

* Why did this decision happen?
* Would the outcome change if the evidence changed?
* Can we replay the exact decision months later?
* Can an auditor independently verify the result?

C-DAG exists to answer those questions.

---

## Evidence

* 100,000+ public financial records processed
* Deterministic replay validation
* Counterfactual generation
* Audit-chain verification
* Fairness diagnostics
* Public benchmark
* DOI-backed technical paper

Benchmark

https://cdag.quest/benchmark

Research

https://doi.org/10.5281/zenodo.19779499

---

## Example Output

Each decision produces structured governance artifacts including:

* decision
* confidence
* causal pathway
* counterfactual scenarios
* replay verification
* audit integrity
* model version
* policy version

These artifacts are designed for engineering, internal audit, compliance, and model-risk review.

---

## Capabilities

* Config-driven causal inference
* Deterministic replay
* Counterfactual explanations
* Tamper-evident audit chains
* Fairness diagnostics
* Batch processing
* FastAPI interface
* CLI interface
* Evidence-pack export

---

## Architecture

Model Configuration

![Down arrow](site/chevrons-down.svg)

Inference

![Down arrow](site/chevrons-down.svg)

Policy Evaluation

![Down arrow](site/chevrons-down.svg)

Counterfactual Analysis

![Down arrow](site/chevrons-down.svg)

Replay Verification

![Down arrow](site/chevrons-down.svg)

Audit Artifact

---

## Public Validation

C-DAG includes reference validation using public mortgage and complaint datasets including:

* Freddie Mac
* Fannie Mae
* HMDA
* CFPB

The reference implementation demonstrates governance workflows using historical public data.

It is **not** a lending system and **does not** make production credit decisions.

---

## Quick Start

```bash
pip install -e ".[dev]"

python -m pytest -q

python -m causal_credit_risk.cli --json-only
```

---

## Documentation

Technical documentation, architecture, API references, governance workflows, and deployment guidance are available in the `/docs` directory.

---

## License

Business Source License 1.1

Commercial production use requires a commercial license from Antiparty, Inc.
