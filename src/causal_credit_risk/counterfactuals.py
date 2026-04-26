"""Intervention-style counterfactual query helpers.

WARNING:
This module supports explainability demos only.
It is not evidence of causal validity for production decisions.
"""

from __future__ import annotations

from typing import Mapping

from causal_credit_risk.inference import ExactInferenceEngine
from causal_credit_risk.schemas import CounterfactualResult, StateRef


def intervention_counterfactual(
    engine: ExactInferenceEngine,
    *,
    outcome_node_id: str,
    outcome_state: StateRef,
    baseline_evidence: Mapping[str, StateRef],
    intervention_evidence: Mapping[str, StateRef],
) -> CounterfactualResult:
    baseline_dict = dict(baseline_evidence)
    intervention_dict = dict(intervention_evidence)

    before_probability = engine.query_probability(
        outcome_node_id, outcome_state, evidence=baseline_dict
    )

    # Evidence on intervened nodes is replaced by the do() action.
    post_intervention_evidence = {
        node_id: state
        for node_id, state in baseline_dict.items()
        if node_id not in intervention_dict
    }
    after_probability = engine.query_probability(
        outcome_node_id,
        outcome_state,
        evidence=post_intervention_evidence,
        interventions=intervention_dict,
    )

    baseline_idx = engine.model.normalize_evidence(baseline_dict)
    intervention_idx = engine.model.normalize_evidence(intervention_dict)
    return CounterfactualResult(
        baseline_evidence=engine.model.denormalize_evidence(baseline_idx),
        intervention_evidence=engine.model.denormalize_evidence(intervention_idx),
        before_probability=float(before_probability),
        after_probability=float(after_probability),
        delta=float(after_probability - before_probability),
    )
