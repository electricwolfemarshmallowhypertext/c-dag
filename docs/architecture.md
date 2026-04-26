# Architecture

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

## Components

- Configs: externalized CPDs and policy parameters
- Model loader and validator: structural checks before runtime use
- Inference engine: exact discrete DAG inference
- Policy layer: action mapping (`APPROVE`/`REVIEW`/`DECLINE`)
- Counterfactual engine: intervention analysis
- Audit generator: regulator-facing structured output
- Replay verifier: deterministic recomputation checks
- Batch runner: row-level processing with error isolation
- CLI/API: operator and integration surfaces
