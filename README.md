![C-DAG feature image](site/cdag-quest-feature.jpg)

# C-DAG

**Replayable causal audit traces for high-risk AI decisions.**

## What is C-DAG?

C-DAG transforms AI decisions into replayable, inspectable, and verifiable audit artifacts for governance, compliance, and model-risk workflows.

Instead of treating AI output as a black box, C-DAG records how a decision was reached, allows deterministic replay, generates counterfactual explanations, and produces tamper-evident audit evidence.

---

## Why does it matter?

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

C-DAG includes reference validation using public mortgage and complaint datasets including:

* Freddie Mac
* Fannie Mae
* HMDA
* CFPB

The reference implementation demonstrates governance workflows using historical public data.

It is **not** a lending system and **does not** make production credit decisions.

---

## Example audit artifact

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

## Architecture

```mermaid
flowchart LR
    C1["Model Configs"] --> ML["Model Loader"]
    C2["Policy Config"] --> ML
    ML --> V["Validator"]
    V --> I["Inference Engine"]
    I --> P["Policy Layer"]
    I --> CF["Counterfactual Engine"]
    P --> A["Audit Generator"]
    CF --> A
    A --> RV["Replay Verifier"]
    A --> BR["Batch Runner"]
    A --> EX["Audit Export"]
    RV --> API["API Surface"]
    BR --> API
    A --> CLI["CLI Surface"]
    RV --> CLI
```

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
