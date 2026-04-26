# Config Schema Reference

This document defines the JSON config contracts for:

- `configs/credit_risk_model.v1.json`
- `configs/decision_policy.v1.json`

The runtime validates these structures on load. Invalid configs fail before inference.

## Model config schema

Top-level fields:

- `model_id` (string)
- `model_version` (string)
- `description` (string, optional)
- `nodes` (array of node objects)
- `cpds` (object keyed by `node_id`)

### Node object

- `node_id` (string, unique)
- `human_label` (string)
- `states` (array of strings, unique, non-empty)
- `parents` (array of strings, each must reference an existing node)
- `mechanism_description` (string)
- `node_type` (enum: `observed`, `inferred`, `outcome`)

### CPD object

- `parents` (array of strings, must exactly match node parent order)
- `outcomes` (array of strings, must exactly match node states order)
- `table` (nested numeric array)

CPD table shape:

- `table.shape == (len(states), len(parent_1_states), len(parent_2_states), ...)`
- Axis 0 is always the outcome axis

Runtime validation rules:

- CPD dimensions match expected shape
- Every value is between 0 and 1
- CPD values sum to 1 across axis 0 for every parent-state combination
- Node references and parent references exist
- DAG is acyclic

### Minimal model example

```json
{
  "model_id": "credit_risk_causal_dag",
  "model_version": "1.0.0",
  "nodes": [
    {
      "node_id": "tenure",
      "human_label": "Employment Tenure",
      "states": ["short", "long"],
      "parents": [],
      "mechanism_description": "Prior over tenure state.",
      "node_type": "observed"
    }
  ],
  "cpds": {
    "tenure": {
      "parents": [],
      "outcomes": ["short", "long"],
      "table": [0.4, 0.6]
    }
  }
}
```

## Policy config schema

Top-level fields:

- `policy_id` (string)
- `policy_version` (string)
- `decline_threshold` (float in `[0, 1]`)
- `manual_review_lower` (float in `[0, 1]`)
- `manual_review_upper` (float in `[0, 1]`)
- `risk_outcome_node` (string; must exist in model config)
- `high_risk_state` (string; must exist in `risk_outcome_node` states)

Runtime validation rules:

- `manual_review_lower <= manual_review_upper`
- `manual_review_upper <= decline_threshold`

### Minimal policy example

```json
{
  "policy_id": "credit_risk_demo_policy",
  "policy_version": "1.0.0",
  "decline_threshold": 0.5,
  "manual_review_lower": 0.35,
  "manual_review_upper": 0.5,
  "risk_outcome_node": "risk",
  "high_risk_state": "high_risk"
}
```
